from ol_core.core.exceptions import ErroConexaoBanco
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_perfis
from ol_core.models.enums.tipo_status_oper import TipoStatusOper

from app.models import Arquivo, ArquivoBaixadoFtp, Pedido, PedidoItem, PedidoOcorrencia
from app.schemas.dashboard import (
    ArquivosPorDiaItem,
    DashboardCards,
    MotivoCancelamentoItem,
    PedidosFaturadosPorDiaItem,
    TopProdutoItem,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

_TODOS = require_perfis("Administrador", "Operador Logístico", "Gerente Comercial")


# Todo o dashboard trabalha com um intervalo explícito "de / até" escolhido
# pelo usuário, ancorado em Pedido.data_pedido (data de envio do pedido,
# extraída do número do pedido OL) — e não em datas de ingestão como
# criado_em/baixado_em. Assim todos os widgets descrevem exatamente a mesma
# população de pedidos, mesmo quando a coleta/importação está processando um
# backlog antigo (situação em que os contadores por data de ingestão sobem e
# os por data de pedido não, o que gerava leituras contraditórias no painel).
#
# Única exceção: o card "Arquivos Recebidos" conta downloads do FTP, e a
# tabela arquivo_baixado_ftp não tem vínculo com pedido — esse segue medido
# por baixado_em, e o card avisa isso ao usuário.

_JANELA_PADRAO_DIAS = 30
_MAX_INTERVALO_DIAS = 366


def _resolver_periodo(data_inicio: Optional[date], data_fim: Optional[date]) -> tuple[datetime, datetime]:
    """Normaliza o intervalo recebido para (início 00:00:00, fim 23:59:59).

    Os dois parâmetros são opcionais: sem nada informado, cai nos últimos
    _JANELA_PADRAO_DIAS dias — o mesmo padrão do filtro anterior."""
    fim = data_fim or datetime.now().date()
    inicio = data_inicio or (fim - timedelta(days=_JANELA_PADRAO_DIAS - 1))

    if inicio > fim:
        raise HTTPException(status_code=422, detail="A data inicial não pode ser maior que a data final.")
    if (fim - inicio).days + 1 > _MAX_INTERVALO_DIAS:
        raise HTTPException(
            status_code=422,
            detail=f"O intervalo selecionado não pode passar de {_MAX_INTERVALO_DIAS} dias.",
        )

    return datetime.combine(inicio, datetime.min.time()), datetime.combine(fim, datetime.max.time())


def _dias_do_periodo(inicio: datetime, fim: datetime) -> list[date]:
    """Lista de todos os dias do intervalo (incluindo os sem nenhum registro)
    — usada pra preencher os gráficos por dia com zero em vez de simplesmente
    pular o dia, o que deixaria os gráficos de linha/barra com "buracos"
    enganosos."""
    primeiro, ultimo = inicio.date(), fim.date()
    return [primeiro + timedelta(days=i) for i in range((ultimo - primeiro).days + 1)]


# ----------------------------------------------------------------------- cards
_SITUACOES_BAIXADO = ["Baixado", "Baixado com Vitamina", "Baixando"]


def _distinct_pedidos_com_arquivo(
    db: Session, inicio: datetime, fim: datetime, tipo: str, situacao: Optional[str] = None
) -> int:
    sub = db.query(Arquivo.numero_pedido_ol).filter(Arquivo.tipo == tipo)
    if situacao:
        sub = sub.filter(Arquivo.situacao == situacao)
    sub = sub.subquery()

    return (
        db.query(func.count(func.distinct(Pedido.numero_pedido_ol)))
        .filter(Pedido.data_pedido.between(inicio, fim), Pedido.numero_pedido_ol.in_(sub))
        .scalar()
        or 0
    )


@router.get("/cards", response_model=DashboardCards)
def cards(
    data_inicio: Optional[date] = Query(None, description="Início do período (data do pedido)"),
    data_fim: Optional[date] = Query(None, description="Fim do período (data do pedido)"),
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    inicio, fim = _resolver_periodo(data_inicio, data_fim)

    # Recebidos: arquivos efetivamente baixados no FTP da Hypera
    total_recebidos = (
        db.query(func.count(ArquivoBaixadoFtp.id))
        .filter(
            ArquivoBaixadoFtp.situacao.in_(_SITUACOES_BAIXADO),
            ArquivoBaixadoFtp.baixado_em.between(inicio, fim),
        )
        .scalar()
        or 0
    )

    # Importados: pedidos efetivamente criados no painel a partir dos arquivos recebidos
    total_importados = (
        db.query(func.count(Pedido.id))
        .filter(Pedido.data_pedido.between(inicio, fim))
        .scalar()
        or 0
    )

    # Pendentes: pedidos cujo status_operacional é literalmente "Verificar"
    # (TipoStatusOper.VERIFICAR — atribuído pelo import/reprocessamento quando
    # há ocorrência não resolvida no momento da validação). Antes este KPI
    # contava por ocorrência em aberto (PedidoOcorrencia.resolvido == False),
    # o que sub-contava pedidos que ficaram parados em "Verificar" — o campo
    # de status é a fonte de verdade usada em todo o resto do sistema
    # (Confecção, badges, etc.), não a contagem de ocorrências.
    total_pendentes = (
        db.query(func.count(Pedido.id))
        .filter(Pedido.data_pedido.between(inicio, fim), Pedido.status_operacional == TipoStatusOper.VERIFICAR.value)
        .scalar()
        or 0
    )

    # Prontos para transmissão: pedidos validados sem pendências, aguardando
    # a transmissão em lote para o DELAGE (TipoStatusOper.PRONTO).
    total_prontos_transmissao = (
        db.query(func.count(Pedido.id))
        .filter(Pedido.data_pedido.between(inicio, fim), Pedido.status_operacional == TipoStatusOper.PRONTO.value)
        .scalar()
        or 0
    )

    # Retornos gerados: pedidos com arquivo de retorno gerado
    total_retornos_gerados = _distinct_pedidos_com_arquivo(db, inicio, fim, "retorno")

    # Espelhos gerados: pedidos com arquivo de espelho (NF) gerado
    total_espelhos_gerados = _distinct_pedidos_com_arquivo(db, inicio, fim, "espelho")

    # Cancelamentos gerados: pedidos com arquivo de cancelamento gerado
    total_cancelamentos_gerados = _distinct_pedidos_com_arquivo(db, inicio, fim, "cancelado")

    return DashboardCards(
        total_recebidos=total_recebidos,
        total_importados=total_importados,
        total_pendentes=total_pendentes,
        total_prontos_transmissao=total_prontos_transmissao,
        total_retornos_gerados=total_retornos_gerados,
        total_espelhos_gerados=total_espelhos_gerados,
        total_cancelamentos_gerados=total_cancelamentos_gerados,
    )


# ----------------------------------------------------------------------- motivos de cancelamento
#
# Não existe um campo estruturado de "motivo" nas ocorrências — só uma
# descrição de texto livre (gerada pelos validators do OL_CORE, ex.: "Cliente
# 12345678000199 não está cadastrado no sistema"). Por isso classificamos a
# descrição por padrões conhecidos, que são os mesmos textos fixos usados em
# ol_core/validators/*.py. Se um novo tipo de ocorrência for criado lá e não
# tiver um padrão aqui, ele cai em "Outros" — não é perdido, só não é
# categorizado ainda.
_PADROES_MOTIVO: list[tuple[re.Pattern, str]] = [
    (re.compile(r"não está cadastrado no sistema"), "Cliente inexistente"),
    (re.compile(r"está bloqueado no sistema"), "Cliente bloqueado"),
    (re.compile(r"está com alvara vencido"), "Alvará do cliente vencido"),
    (re.compile(r"não está cadastrada no Delage: "), "Condição inexistente"),
    (re.compile(r"não possui data de validade"), "Condição sem data de validade"),
    (re.compile(r"Condição .* está expirada"), "Condição vencida"),
    (re.compile(r"não está com a flag BBS ativa"), "Condição sem flag BBS"),
    (re.compile(r"não está com a flag acessivel_outras_cond ativa"), "Condição sem acesso a outras condições"),
    (re.compile(r"não está com a flag acessa_outras_cond ativa"), "Condição mãe sem flag de acesso"),
    (re.compile(r"não está cadastrado na condição"), "Cliente fora da condição"),
    (re.compile(r"Produto não está cadastrado no Delage"), "Produto inexistente"),
    (re.compile(r"Produto não está em estoque"), "Produto sem estoque"),
    (re.compile(r"não está configurado na condição"), "Produto fora da condição"),
    (re.compile(r"menor que o configurado na condicao"), "Quantidade abaixo da faixa da condição"),
    (re.compile(r"Desconto do .* maior que o configurado"), "Desconto acima do permitido"),
    (re.compile(r"abaixo do mínimo"), "Valor do pedido abaixo do mínimo"),
]


def _classificar_motivo(descricao: Optional[str]) -> str:
    texto = descricao or ""
    for padrao, rotulo in _PADROES_MOTIVO:
        if padrao.search(texto):
            return rotulo
    return "Outros"


@router.get("/motivos-cancelamento", response_model=list[MotivoCancelamentoItem])
def motivos_cancelamento(
    data_inicio: Optional[date] = Query(None, description="Início do período (data do pedido)"),
    data_fim: Optional[date] = Query(None, description="Fim do período (data do pedido)"),
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    """
    Conta as ocorrências de validação (as mesmas exibidas na tela de
    Ocorrências) dos pedidos do período, agrupadas por motivo — o motivo é
    inferido a partir do texto da descrição, já que não existe um campo
    estruturado equivalente.

    O recorte é por Pedido.data_pedido (e não por PedidoOcorrencia.criado_em),
    para o gráfico descrever a mesma população de pedidos dos cards.
    """
    inicio, fim = _resolver_periodo(data_inicio, data_fim)

    descricoes = (
        db.query(PedidoOcorrencia.descricao)
        .join(Pedido, Pedido.numero_pedido_ol == PedidoOcorrencia.numero_pedido_ol)
        .filter(Pedido.data_pedido.between(inicio, fim))
        .all()
    )

    contagem: dict[str, int] = defaultdict(int)
    for (descricao,) in descricoes:
        contagem[_classificar_motivo(descricao)] += 1

    resultado = [MotivoCancelamentoItem(motivo=m, total=t) for m, t in contagem.items()]
    resultado.sort(key=lambda i: i.total, reverse=True)
    return resultado


# ----------------------------------------------------------------------- arquivos enviados por dia

@router.get("/arquivos-enviados-por-dia", response_model=list[ArquivosPorDiaItem])
def arquivos_enviados_por_dia(
    data_inicio: Optional[date] = Query(None, description="Início do período (data do pedido)"),
    data_fim: Optional[date] = Query(None, description="Fim do período (data do pedido)"),
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    """
    Conta os arquivos de Retorno/Espelho/Cancelamento que chegaram à situação
    "Enviado", agrupados pela DATA DO PEDIDO a que pertencem. Um mesmo pedido
    pode gerar mais de um arquivo desses ao longo do tempo (reenvio,
    recriação), então aqui contamos arquivos, não pedidos distintos —
    diferente dos cards do topo do dashboard.

    O eixo do gráfico é a data do pedido (não a data de geração do arquivo)
    para acompanhar o mesmo recorte dos demais widgets: o arquivo de um
    pedido de 05/08 aparece em 05/08, mesmo que tenha sido gerado semanas
    depois num reprocessamento de backlog.
    """
    inicio, fim = _resolver_periodo(data_inicio, data_fim)

    linhas = (
        db.query(
            func.date(Pedido.data_pedido).label("dia"),
            Arquivo.tipo,
            func.count(Arquivo.id).label("total"),
        )
        .join(Pedido, Pedido.numero_pedido_ol == Arquivo.numero_pedido_ol)
        .filter(Arquivo.situacao == "Enviado", Pedido.data_pedido.between(inicio, fim))
        .group_by(func.date(Pedido.data_pedido), Arquivo.tipo)
        .all()
    )

    por_dia: dict[date, dict[str, int]] = defaultdict(lambda: {"retorno": 0, "espelho": 0, "cancelamento": 0})
    for dia, tipo, total in linhas:
        dia = dia if isinstance(dia, date) else datetime.strptime(str(dia), "%Y-%m-%d").date()
        tipo_norm = (tipo or "").lower()
        if tipo_norm == "cancelado":
            tipo_norm = "cancelamento"
        if tipo_norm in por_dia[dia]:
            por_dia[dia][tipo_norm] += total

    return [
        ArquivosPorDiaItem(data=dia, **por_dia.get(dia, {"retorno": 0, "espelho": 0, "cancelamento": 0}))
        for dia in _dias_do_periodo(inicio, fim)
    ]


# ----------------------------------------------------------------------- pedidos faturados por dia

@router.get("/pedidos-faturados-por-dia", response_model=list[PedidosFaturadosPorDiaItem])
def pedidos_faturados_por_dia(
    data_inicio: Optional[date] = Query(None, description="Início do período (data do pedido)"),
    data_fim: Optional[date] = Query(None, description="Fim do período (data do pedido)"),
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    """
    Conta pedidos com status_erp = "Faturado", por dia.

    Observação: hoje NENHUM processo deste repositório atribui
    status_erp = "Faturado" a um pedido (é um valor só consultado, nunca
    atribuído — achado já registrado no card de auditoria sobre status
    documentados que nunca ocorrem). Então este gráfico tende a vir vazio até
    que a sincronização com o ERP que atualiza esse status seja implementada
    ou identificada.

    O eixo é a data do pedido (Pedido.data_pedido), igual ao resto do
    dashboard — não existe coluna própria de data de faturamento, e usar
    "atualizado_em" faria este gráfico cair fora do intervalo selecionado.
    """
    inicio, fim = _resolver_periodo(data_inicio, data_fim)

    linhas = (
        db.query(
            func.date(Pedido.data_pedido).label("dia"),
            func.count(Pedido.id).label("total"),
        )
        .filter(Pedido.status_erp == "Pedido Concluido", Pedido.data_pedido.between(inicio, fim))
        .group_by(func.date(Pedido.data_pedido))
        .all()
    )

    por_dia: dict[date, int] = {}
    for dia, total in linhas:
        dia = dia if isinstance(dia, date) else datetime.strptime(str(dia), "%Y-%m-%d").date()
        por_dia[dia] = total

    return [PedidosFaturadosPorDiaItem(data=dia, total=por_dia.get(dia, 0)) for dia in _dias_do_periodo(inicio, fim)]


# ----------------------------------------------------------------------- top 10 produtos

@router.get("/top-produtos", response_model=list[TopProdutoItem])
def top_produtos(
    data_inicio: Optional[date] = Query(None, description="Início do período (data do pedido)"),
    data_fim: Optional[date] = Query(None, description="Fim do período (data do pedido)"),
    limite: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    """
    Produtos mais solicitados (soma de quantidade_solicitada) no período,
    pela quantidade de vezes que apareceram em itens de pedido. A descrição
    do produto é buscada no ERP (SQL Server) por EAN — se o ERP estiver
    indisponível no momento da chamada, o produto aparece só com o EAN.
    """
    inicio, fim = _resolver_periodo(data_inicio, data_fim)

    linhas = (
        db.query(
            PedidoItem.ean,
            func.sum(PedidoItem.quantidade_solicitada).label("total"),
        )
        .join(Pedido, Pedido.numero_pedido_ol == PedidoItem.numero_pedido_ol)
        .filter(Pedido.data_pedido.between(inicio, fim), PedidoItem.ean.isnot(None))
        .group_by(PedidoItem.ean)
        .order_by(func.sum(PedidoItem.quantidade_solicitada).desc())
        .limit(limite)
        .all()
    )

    resultado = []
    for ean, total in linhas:
        descricao = None
        try:
            from ol_core.database.sqlserver.contexto_produto import resgatar_produto

            produto = resgatar_produto(ean)
            if produto:
                descricao = produto.get("descricao")
        except ErroConexaoBanco:
            raise
        except Exception:
            # ERP indisponível ou EAN não encontrado — mantém só o EAN, não quebra o gráfico
            descricao = None

        resultado.append(TopProdutoItem(ean=ean, descricao=descricao, quantidade_solicitada=int(total or 0)))

    return resultado
