"""Consultas de Rastreamento e Histórico (status dos arquivos de retorno,
espelho e cancelamento) — usadas pela listagem, pela exportação xlsx e pelo
reenvio em lote, para que as três enxerguem o mesmo conjunto de pedidos."""
from datetime import date, datetime
from typing import Optional, cast

from sqlalchemy import case, exists, func, null, or_, select
from sqlalchemy.orm import Session, aliased, joinedload, selectinload

from app.models import Arquivo, Pedido
from app.services import operacoes
from app.services.operacoes.exibicao import _ROTULO_TIPO, _SITUACOES_RECONHECIDAS
from ol_core.models.enums.tipo_arquivo import TipoArquivo
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from ol_core.models import regras_status

from ._comum import _filtrar_busca


def _ultima_situacao_arquivo_sql(tipo: str):
    """Subconsulta correlacionada: `situacao` do arquivo mais recente do tipo
    para o pedido da linha (mesmo critério de `_montar_status_arquivos`: maior
    criado_em, desempate pelo maior id; criado_em NULL perde)."""
    a = aliased(Arquivo)
    return (
        select(a.situacao)
        .where(a.numero_pedido_ol == Pedido.numero_pedido_ol, func.lower(a.tipo) == tipo)
        .order_by(a.criado_em.desc(), a.id.desc())
        .limit(1)
        .correlate(Pedido)
        .scalar_subquery()
    )


def _status_arquivo_sql(tipo: str):
    """Versão SQL de `operacoes.mapear_status_arquivo` aplicada ao arquivo mais
    recente do tipo. Precisa ficar em sincronia com ela: é o que deixa o filtro
    de status rodar no banco (COUNT + LIMIT/OFFSET) em vez de carregar todos
    os pedidos para filtrar e paginar em Python."""
    rotulo = _ROTULO_TIPO[tipo]
    situacao = _ultima_situacao_arquivo_sql(tipo)
    normalizada = func.lower(func.trim(situacao))
    return case(
        (situacao.in_(_SITUACOES_RECONHECIDAS), situacao),
        (normalizada == "erro", TipoStatusOper.FALHA.value),
        (normalizada.in_(("em criação", "recriando")), f"Gerando {rotulo}"),
        (normalizada == "gerado", f"{rotulo} Gerado"),
        (normalizada == "enviado", f"{rotulo} Enviado"),
        else_=null(),
    )


def _status_cancelamento_sql():
    """Coluna Cancelamento: o arquivo de cancelamento, se existir; senão o
    fallback do status_operacional (igual a `_montar_status_arquivos`)."""
    a = aliased(Arquivo)
    tem_arquivo = (
        exists()
        .where(a.numero_pedido_ol == Pedido.numero_pedido_ol, func.lower(a.tipo) == TipoArquivo.CANCELADO.value)
        .correlate(Pedido)
    )
    return case(
        (tem_arquivo, _status_arquivo_sql(TipoArquivo.CANCELADO.value)),
        (Pedido.status_operacional == TipoStatusOper.CANCELADO.value, TipoStatusOper.CANCELADO.value),
        else_=null(),
    )


def _filtro_status_rastreamento(status: str):
    """Filtro "Status" do Rastreamento, em SQL. A collation do banco
    (utf8mb4_unicode_ci) já compara sem diferenciar maiúsculas, como o filtro
    antigo em Python fazia com .lower()."""
    cancelamento = _status_cancelamento_sql()
    if status.strip().lower() == "cancelado":
        return cancelamento == "Cancelado"
    return or_(
        _status_arquivo_sql(TipoArquivo.RETORNO.value) == status,
        _status_arquivo_sql(TipoArquivo.ESPELHO.value) == status,
        cancelamento == status,
    )


def _query_rastreamento(
    db: Session,
    numero_pedido_ol: Optional[str],
    cnpj_cliente: Optional[str],
    data_inicio: Optional[date],
    data_fim: Optional[date],
    nome_arquivo: Optional[str] = None,
    busca: Optional[str] = None,
    status: Optional[str] = None,
):
    """Pedidos "em andamento": já transmitidos, mas que ainda não chegaram a um
    estágio final de faturamento (Processo Concluido / Pedido Cancelado — ver
    TipoStatusErp). Assim que o pedido chega lá, ele sai do Rastreamento e só
    aparece no Histórico (endpoint /pedidos/historico, `_filtrar_historico`
    abaixo). Devolve a query (sem ORDER BY) para quem chama paginar no banco."""
    q = (
        db.query(Pedido)
        .options(joinedload(Pedido.industria), joinedload(Pedido.usuario_analisou), selectinload(Pedido.arquivos))
        .filter(Pedido.status_erp != TipoStatusErp.NAO_TRANSMITIDO.value)
        .filter(Pedido.status_erp.notin_(regras_status.ERP_ENCERRADO))
    )

    q = _filtrar_busca(q, busca)
    if numero_pedido_ol:
        q = q.filter(Pedido.numero_pedido_ol.ilike(f"%{numero_pedido_ol}%"))
    if cnpj_cliente:
        q = q.filter(Pedido.cnpj_cliente.ilike(f"%{cnpj_cliente}%"))
    if nome_arquivo:
        q = q.filter(Pedido.nome_arquivo == nome_arquivo.strip())
    if data_inicio:
        q = q.filter(Pedido.data_pedido >= datetime.combine(data_inicio, datetime.min.time()))
    if data_fim:
        q = q.filter(Pedido.data_pedido <= datetime.combine(data_fim, datetime.max.time()))
    if status:
        q = q.filter(_filtro_status_rastreamento(status))
    return q


def _filtrar_rastreamento(
    db: Session,
    numero_pedido_ol: Optional[str],
    cnpj_cliente: Optional[str],
    data_inicio: Optional[date],
    data_fim: Optional[date],
    nome_arquivo: Optional[str] = None,
    busca: Optional[str] = None,
    status: Optional[str] = None,
) -> list[Pedido]:
    """Todos os pedidos do recorte (sem paginação) — usado pelo export."""
    return (
        _query_rastreamento(db, numero_pedido_ol, cnpj_cliente, data_inicio, data_fim, nome_arquivo, busca, status)
        .order_by(Pedido.atualizado_em.desc())
        .all()
    )


def _montar_status_arquivos(pedido: Pedido) -> tuple[Optional[str], Optional[str], Optional[str], bool]:
    """Retorna (retorno_status, espelho_status, cancelamento_status, falha_geral) para um pedido."""
    tipos_rastreados = {TipoArquivo.RETORNO.value, TipoArquivo.ESPELHO.value, TipoArquivo.CANCELADO.value}

    # Mais recente = maior criado_em, desempate pelo maior id, criado_em NULL
    # perde — o MESMO critério de `_ultima_situacao_arquivo_sql`, para o status
    # exibido bater com o filtro feito no banco.
    def _recencia(arq: Arquivo):
        return (arq.criado_em or datetime.min, arq.id or 0)

    ultimo_por_tipo: dict[str, Arquivo] = {}
    for a in pedido.arquivos:
        tipo_norm = (a.tipo or "").lower()
        if tipo_norm not in tipos_rastreados:
            continue
        atual = ultimo_por_tipo.get(tipo_norm)
        if atual is None or _recencia(a) > _recencia(atual):
            ultimo_por_tipo[tipo_norm] = a

    retorno_status = None
    arquivo_retorno = ultimo_por_tipo.get(TipoArquivo.RETORNO.value)
    if arquivo_retorno:
        retorno_status = operacoes.mapear_status_arquivo(TipoArquivo.RETORNO.value, cast(str, arquivo_retorno.situacao))

    espelho_status = None
    arquivo_espelho = ultimo_por_tipo.get(TipoArquivo.ESPELHO.value)
    if arquivo_espelho:
        espelho_status = operacoes.mapear_status_arquivo(TipoArquivo.ESPELHO.value, cast(str, arquivo_espelho.situacao))

    cancelamento_status = None
    arquivo_cancelamento = ultimo_por_tipo.get(TipoArquivo.CANCELADO.value)
    if arquivo_cancelamento:
        cancelamento_status = operacoes.mapear_status_arquivo(TipoArquivo.CANCELADO.value, cast(str, arquivo_cancelamento.situacao))
    elif cast(Optional[str], pedido.status_operacional) == TipoStatusOper.CANCELADO.value:
        cancelamento_status = TipoStatusOper.CANCELADO.value

    # Triângulo de alerta geral: só quando o pedido está em falha e NENHUMA das
    # 3 colunas já está mostrando essa falha (evita indicar a mesma falha duas vezes).
    status_operacional = cast(Optional[str], pedido.status_operacional)
    falha_geral: bool = status_operacional in regras_status.FALHAS_GERACAO and not any(
        s in regras_status.FALHAS_GERACAO for s in (retorno_status, espelho_status, cancelamento_status)
    )
    return retorno_status, espelho_status, cancelamento_status, falha_geral


def _filtrar_historico(
    db: Session,
    numero_pedido_ol: Optional[str],
    cnpj_cliente: Optional[str],
    industria_nome: Optional[str],
    status_erp: Optional[str],
    data_inicio: Optional[date],
    data_fim: Optional[date],
    nome_arquivo: Optional[str] = None,
    busca: Optional[str] = None,
):
    """Pedidos com o fluxo encerrado (Processo Concluido ou Pedido Cancelado —
    ver TipoStatusErp). Contraparte de `_filtrar_rastreamento`: o filtro por
    status_erp é feito em SQL (indexado), então a paginação abaixo é real —
    ao contrário do que a tela de Histórico fazia antes (buscar um teto fixo
    de linhas mais recentes e filtrar "concluído" no cliente, o que fazia
    pedidos concluídos há mais tempo somem da lista conforme o volume de
    pedidos ativos crescia)."""
    q = (
        db.query(Pedido)
        .options(joinedload(Pedido.industria), joinedload(Pedido.usuario_analisou), selectinload(Pedido.arquivos))
        .filter(Pedido.status_erp.in_(regras_status.ERP_ENCERRADO))
    )
    q = _filtrar_busca(q, busca)
    if numero_pedido_ol:
        q = q.filter(Pedido.numero_pedido_ol.ilike(f"%{numero_pedido_ol}%"))
    if cnpj_cliente:
        q = q.filter(Pedido.cnpj_cliente.ilike(f"%{cnpj_cliente}%"))
    if nome_arquivo:
        q = q.filter(Pedido.nome_arquivo == nome_arquivo.strip())
    if industria_nome:
        q = q.filter(Pedido.industria.has(nome=industria_nome))
    if status_erp:
        q = q.filter(Pedido.status_erp == status_erp)
    if data_inicio:
        q = q.filter(Pedido.data_pedido >= datetime.combine(data_inicio, datetime.min.time()))
    if data_fim:
        q = q.filter(Pedido.data_pedido <= datetime.combine(data_fim, datetime.max.time()))
    return q
