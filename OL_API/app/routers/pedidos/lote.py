"""Operações em lote (/pedidos/lote/...): reprocessamento, retorno, espelho,
cancelamento, transmissão e reenvio — cada uma com seu /preview."""
from datetime import date, datetime
from typing import Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.database import get_db
from app.models import Arquivo, Parametro, Pedido, PedidoOcorrencia
from app.schemas.pedido import (
    LoteBody,
    LotePreview,
    LoteResultItem,
    LoteResultado,
    ReenviarLoteBody,
    ReenvioPreview,
    ReprocessarLoteBody,
    TransmitirLoteBody,
)
from app.services import operacoes
from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.logger import contexto_pedido, logger
from ol_core.models.enums.tipo_arquivo import TipoArquivo
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from ol_core.models import regras_status

from ._comum import (
    _OPERACIONAL,
    _envio_somente_pronto,
    _fora_de_analise,
    _marcar_transmitindo,
)
from ._rastreamento import _filtrar_historico

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


def _lote_executar(pedidos, fn, usuario_id: int) -> LoteResultado:
    try:
        detalhes: list[LoteResultItem] = []
        for p in pedidos:
            try:
                with contexto_pedido(p.numero_pedido_ol):
                    res = fn(p, usuario_id)
                detalhes.append(LoteResultItem(
                    numero_pedido_ol=p.numero_pedido_ol or '',
                    sucesso=bool(res.get('sucesso', True)),
                    mensagem=res.get('mensagem', 'OK'),
                ))
            except ErroConexaoBanco:
                raise
            except Exception as e:
                detalhes.append(LoteResultItem(
                    numero_pedido_ol=p.numero_pedido_ol or '',
                    sucesso=False,
                    mensagem=str(e),
                ))
        ok = sum(1 for d in detalhes if d.sucesso)
        return LoteResultado(total=len(detalhes), sucesso=ok, falha=len(detalhes) - ok, detalhes=detalhes)
    except ErroConexaoBanco:
        raise
    except Exception as e:
        return LoteResultado(total=0, sucesso=0, falha=0, detalhes=[LoteResultItem(
            numero_pedido_ol='',
            sucesso=False,
            mensagem=str(e),
        )])


# Filtros das operações em lote.
#
# Cada filtro abaixo é usado PELAS DUAS pontas: o POST que executa e o GET
# /preview que só conta. Ter uma função única é o que garante que o número
# mostrado na confirmação ("X pedidos serão reprocessados") é exatamente o
# conjunto que será processado — com duas queries separadas, qualquer ajuste
# numa delas passaria a mentir para o operador sem quebrar nada visivelmente.


def _periodo_e_cliente(q, data_inicio: Optional[date], data_fim: Optional[date], cnpj_cliente: Optional[str]):
    """Filtros comuns a todas as operações em lote."""
    if data_inicio:
        q = q.filter(Pedido.data_pedido >= datetime.combine(data_inicio, datetime.min.time()))
    if data_fim:
        q = q.filter(Pedido.data_pedido <= datetime.combine(data_fim, datetime.max.time()))
    if cnpj_cliente:
        q = q.filter(Pedido.cnpj_cliente.ilike(f"%{cnpj_cliente}%"))
    return q


def _query_lote_reprocessar(db: Session, data_inicio, data_fim, cnpj_cliente, apenas_erro: bool):
    # Pedido em análise fica de fora: reprocessá-lo derrubaria a análise sem
    # ninguém perceber. Quem reprocessa é o encerramento da análise.
    q = (
        db.query(Pedido)
        .filter(Pedido.status_erp == TipoStatusErp.NAO_TRANSMITIDO.value)
        .filter(_fora_de_analise())
    )
    q = _periodo_e_cliente(q, data_inicio, data_fim, cnpj_cliente)
    if apenas_erro:
        q = q.filter(
            Pedido.status_operacional.in_(regras_status.REPROCESSAR_EM_LOTE_COM_ERRO)
        )
    return q


def _query_lote_retorno(db: Session, data_inicio, data_fim, cnpj_cliente):
    q = (
        db.query(Pedido)
        .filter(Pedido.status_erp != TipoStatusErp.NAO_TRANSMITIDO.value)
        .filter(Pedido.status_erp.notin_(regras_status.ERP_ENCERRADO))
    )
    return _periodo_e_cliente(q, data_inicio, data_fim, cnpj_cliente)


def _query_lote_espelho(db: Session, data_inicio, data_fim, cnpj_cliente):
    q = db.query(Pedido).filter(Pedido.status_erp.in_(regras_status.ERP_ESPELHO_EM_LOTE))
    return _periodo_e_cliente(q, data_inicio, data_fim, cnpj_cliente)


def _query_lote_cancelamento(db: Session, data_inicio, data_fim, cnpj_cliente):
    q = db.query(Pedido).filter(Pedido.status_erp.in_(regras_status.ERP_CANCELAMENTO_EM_LOTE))
    return _periodo_e_cliente(q, data_inicio, data_fim, cnpj_cliente)


def _query_lote_transmitir(db: Session, apenas_sem_ocorrencia: bool):
    # Pedido em análise nunca entra no lote — é o ponto da feature: ninguém
    # transmite por acidente o pedido que outro operador está analisando.
    q = (
        db.query(Pedido)
        .filter(Pedido.status_erp == TipoStatusErp.NAO_TRANSMITIDO.value)
        .filter(_fora_de_analise())
    )
    if _envio_somente_pronto(db):
        # Parâmetro BLOQUEAR_ENVIO_PEDIDO_VERIFICAR ligado: só "Pronto" entra no
        # lote — o preview (/lote/transmitir/preview) usa esta mesma query, então
        # a contagem confirmada pelo usuário é a do envio.
        q = q.filter(Pedido.status_operacional == TipoStatusOper.PRONTO.value)
    if apenas_sem_ocorrencia:
        subq = (
            select(PedidoOcorrencia.numero_pedido_ol)
            .where(PedidoOcorrencia.resolvido == False)  # noqa: E712
            .distinct()
        )
        q = q.filter(~Pedido.numero_pedido_ol.in_(subq))
    return q


@router.post("/lote/reprocessar", response_model=LoteResultado)
def reprocessar_lote_nao_transmitidos( body: ReprocessarLoteBody = ReprocessarLoteBody(), db: Session = Depends(get_db), current_user=Depends(_OPERACIONAL),):
    """Reprocessa pedidos com status_erp 'Não Transmitido' — por período, só com erro, ou todos."""
    q = _query_lote_reprocessar(db, body.data_inicio, body.data_fim, body.cnpj_cliente, body.apenas_erro).options(
        joinedload(Pedido.industria), selectinload(Pedido.arquivos)
    )
    pedidos = q.all()

    # Toda a fila é marcada como "Aguardando Reprocessamento" antes de o loop
    # começar. O processamento é um pedido por vez: sem esta marcação, quem
    # ainda não chegou na vez continuaria exibindo o status antigo
    # (Verificar/Falha), sem nenhum sinal de que já está na fila. Cada pedido
    # passa para "Reprocessando" quando sua vez chega (em executar_reprocessar).
    if pedidos:
        agora = datetime.now()
        for p in pedidos:
            setattr(p, "status_operacional", TipoStatusOper.AGUARDANDO_REPROCESSANDO.value)
            setattr(p, "atualizado_em", agora)
        db.commit()

    return _lote_executar(pedidos, operacoes.executar_reprocessar, current_user.id)


@router.get("/lote/reprocessar/preview", response_model=LotePreview)
def preview_lote_reprocessar(
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    cnpj_cliente: Optional[str] = Query(None),
    apenas_erro: bool = Query(False),
    db: Session = Depends(get_db),
    _user=Depends(_OPERACIONAL),
):
    """Quantos pedidos o reprocessamento em lote afetaria — só conta, não executa."""
    return LotePreview(total=_query_lote_reprocessar(db, data_inicio, data_fim, cnpj_cliente, apenas_erro).count())


@router.post("/lote/retorno", response_model=LoteResultado)
def retorno_por_periodo( body: LoteBody, db: Session = Depends(get_db), current_user=Depends(_OPERACIONAL),):
    """Gera retorno para pedidos transmitidos no período informado (exclui os
    que já concluíram o fluxo — Processo Concluido / Pedido Cancelado)."""
    q = _query_lote_retorno(db, body.data_inicio, body.data_fim, body.cnpj_cliente).options(
        joinedload(Pedido.industria), selectinload(Pedido.arquivos)
    )
    return _lote_executar(q.all(), operacoes.executar_gerar_retorno, current_user.id)


@router.get("/lote/retorno/preview", response_model=LotePreview)
def preview_lote_retorno(
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    cnpj_cliente: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(_OPERACIONAL),
):
    """Quantos pedidos a geração de retorno em lote afetaria — só conta."""
    return LotePreview(total=_query_lote_retorno(db, data_inicio, data_fim, cnpj_cliente).count())


@router.post("/lote/espelho", response_model=LoteResultado)
def espelho_por_periodo(body: LoteBody, db: Session = Depends(get_db), current_user=Depends(_OPERACIONAL),):
    """Gera espelho para pedidos com Retorno já gerado (Aguardando Faturamento)
    no período informado."""
    q = _query_lote_espelho(db, body.data_inicio, body.data_fim, body.cnpj_cliente).options(
        joinedload(Pedido.industria)
    )
    return _lote_executar(q.all(), operacoes.executar_gerar_espelho, current_user.id)


@router.get("/lote/espelho/preview", response_model=LotePreview)
def preview_lote_espelho(
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    cnpj_cliente: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(_OPERACIONAL),
):
    """Quantos pedidos a geração de espelho em lote afetaria — só conta."""
    return LotePreview(total=_query_lote_espelho(db, data_inicio, data_fim, cnpj_cliente).count())


@router.post("/lote/cancelamento", response_model=LoteResultado)
def cancelamento_por_periodo(body: LoteBody, db: Session = Depends(get_db), current_user=Depends(_OPERACIONAL),):
    """Registra cancelamento para pedidos no período informado — elegíveis são
    os que já transmitiram mas ainda não faturaram nem cancelaram (Transmitido
    ou Aguardando Faturamento)."""
    q = _query_lote_cancelamento(db, body.data_inicio, body.data_fim, body.cnpj_cliente).options(
        joinedload(Pedido.industria)
    )
    return _lote_executar(q.all(), operacoes.executar_cancelamento, current_user.id)


@router.get("/lote/cancelamento/preview", response_model=LotePreview)
def preview_lote_cancelamento(
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    cnpj_cliente: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(_OPERACIONAL),
):
    """Quantos pedidos o cancelamento em lote afetaria — só conta."""
    return LotePreview(total=_query_lote_cancelamento(db, data_inicio, data_fim, cnpj_cliente).count())


def _transmitir_pedido(p: Pedido, db: Session, usuario_id: int, somente_pronto: bool = False) -> LoteResultItem:
    """Copia o arquivo de um pedido pra pasta_entrada da indústria e atualiza
    o status — usado no loop do /lote/transmitir (isola falhas por item: uma
    exceção aqui marca só aquele pedido como Falha e segue o lote, ao invés
    de derrubar a rota inteira). A transmissão individual (/{id}/transmitir)
    tem seu próprio contrato de erro e não usa esta função — ver endpoint
    `transmitir` abaixo.
    """
    try:
        # Marca "Transmitindo" e persiste antes de depositar o arquivo na
        # pasta de entrada — como o commit final do lote só acontecia no
        # fim de todo o loop, esse estado nunca chegava a ser gravado.
        # Atômico: o pedido pode ter entrado em análise depois de a lista do
        # lote ser montada (o loop dura o tempo de copiar todos os arquivos).
        if not _marcar_transmitindo(p, db, somente_pronto=somente_pronto):
            # `_marcar_transmitindo` já releu o pedido: o status atual diz o motivo.
            em_analise = cast(Optional[str], p.status_operacional) == TipoStatusOper.EM_ANALISE.value
            return LoteResultItem(
                numero_pedido_ol=getattr(p, "numero_pedido_ol") or '',
                sucesso=False,
                mensagem=(
                    "Pedido em análise — não foi transmitido."
                    if em_analise
                    else "Envio bloqueado pela parametrização: só pedidos 'Pronto' são transmitidos — não foi transmitido."
                ),
            )

        res = operacoes.executar_transmitir(p, usuario_id)

        setattr(p, "status_erp", TipoStatusErp.TRANSMITIDO.value)
        setattr(p, "status_operacional", TipoStatusOper.TRANSMITIDO.value)
        setattr(p, "transmitido_em", datetime.now())
        setattr(p, "atualizado_em", datetime.now())
        db.commit()
        return LoteResultItem(
            numero_pedido_ol=getattr(p, "numero_pedido_ol") or '',
            sucesso=True,
            mensagem=res.get('mensagem', 'Transmitido com sucesso.'),
        )
    except ErroConexaoBanco:
        raise
    except Exception as e:
        setattr(p, "status_operacional", TipoStatusOper.FALHA.value)
        setattr(p, "atualizado_em", datetime.now())
        db.commit()
        return LoteResultItem(
            numero_pedido_ol=getattr(p, "numero_pedido_ol") or '',
            sucesso=False,
            mensagem=str(e),
        )


@router.post("/lote/transmitir", response_model=LoteResultado)
def transmitir_lote(body: TransmitirLoteBody, db: Session = Depends(get_db), current_user=Depends(_OPERACIONAL),):
    """Copia arquivos 'Não Transmitidos' para a pasta_entrada da indústria."""
    try:
        q = _query_lote_transmitir(db, body.apenas_sem_ocorrencia).options(
            joinedload(Pedido.industria), selectinload(Pedido.arquivos)
        )
        pedidos = q.all()
        somente_pronto = _envio_somente_pronto(db)
        detalhes: list[LoteResultItem] = [
            _transmitir_pedido(p, db, current_user.id, somente_pronto=somente_pronto) for p in pedidos
        ]

        ok = sum(1 for d in detalhes if d.sucesso)
        return LoteResultado(total=len(detalhes), sucesso=ok, falha=len(detalhes) - ok, detalhes=detalhes)
    except ErroConexaoBanco:
        raise
    except Exception as err:
        db.rollback()
        logger.exception(err)
        raise HTTPException(status_code=500, detail=str(err))


# Aceita os valores de TipoArquivo e também "cancelamento", que é como a
# operação é chamada na interface (o tipo gravado na tabela é "cancelado").
_TIPOS_REENVIO = {
    TipoArquivo.RETORNO.value: TipoArquivo.RETORNO.value,
    TipoArquivo.ESPELHO.value: TipoArquivo.ESPELHO.value,
    TipoArquivo.CANCELADO.value: TipoArquivo.CANCELADO.value,
    "cancelamento": TipoArquivo.CANCELADO.value,
}


# Teto de arquivos por disparo de reenvio. Reenvio é síncrono (FTP + cópia por
# arquivo), então um período largo derrubaria a requisição no meio do lote,
# deixando o operador sem saber o que saiu. O teto é parâmetro de banco
# (tela de Parametrização) e não constante de código justamente porque o
# volume aceitável depende da janela de operação, não do deploy.
_CHAVE_LIMITE_REENVIO = "limitador_de_envio"


_LIMITE_REENVIO_PADRAO = 250


def _limite_reenvio(db: Session) -> int:
    """Lê `limitador_de_envio` da tabela `parametro`.

    Parâmetro ausente, vazio, não-numérico ou <= 0 cai no padrão em vez de
    explodir: um valor ruim na parametrização não pode ser o que impede um
    reenvio de acontecer."""
    p = db.query(Parametro).filter(Parametro.chave == _CHAVE_LIMITE_REENVIO).first()
    try:
        valor = int((p.valor or "").strip()) if p else 0
    except (TypeError, ValueError):
        logger.warning(
            f"[reenvio] Parâmetro '{_CHAVE_LIMITE_REENVIO}' com valor inválido "
            f"({p.valor!r}); usando o padrão {_LIMITE_REENVIO_PADRAO}."
        )
        return _LIMITE_REENVIO_PADRAO
    return valor if valor > 0 else _LIMITE_REENVIO_PADRAO


def _query_lote_reenviar(
    db: Session,
    tipo: str,
    data_inicio: Optional[date],
    data_fim: Optional[date],
    industria_nome: Optional[str],
    status_erp: Optional[str],
):
    """Pedidos alcançados pelo reenvio por período, para UM tipo de arquivo.

    Reusa `_filtrar_historico` de propósito: o que é reenviado tem que ser
    exatamente o que a tela de Histórico lista naquele recorte. O filtro de
    `arquivos.any` é por tipo — um pedido concluído sem cancelamento não entra
    na conta de um reenvio de cancelamento. Sem isso o preview prometeria um
    número que viraria uma parede de falhas na execução."""
    # Por nome: posicional aqui já deslocou os argumentos uma vez (indústria
    # caía em status_erp e data_fim em nome_arquivo).
    q = _filtrar_historico(
        db, numero_pedido_ol=None, cnpj_cliente=None, industria_nome=industria_nome,
        status_erp=status_erp, data_inicio=data_inicio, data_fim=data_fim,
    )
    return q.filter(Pedido.arquivos.any(Arquivo.tipo == tipo))


def _resolver_tipo_reenvio(bruto: Optional[str]) -> str:
    """Um reenvio é sempre de um tipo só.

    Não há valor coringa ("todos"): reenvio escreve na pasta da indústria e
    dispara FTP, então o operador declara o que vai sair. Um tipo desconhecido
    para aqui, com 422, em vez de virar um lote silenciosamente vazio."""
    tipo = _TIPOS_REENVIO.get((bruto or "").strip().lower())
    if not tipo:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Tipo de arquivo inválido para reenvio: '{bruto}'. "
                f"Informe retorno, espelho ou cancelamento."
            ),
        )
    return tipo


@router.get("/lote/reenviar/preview", response_model=ReenvioPreview)
def preview_lote_reenviar(
    tipo: str = Query(..., description="retorno, espelho ou cancelamento"),
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    industria_nome: Optional[str] = Query(None),
    status_erp: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(_OPERACIONAL),
):
    """Quantos pedidos o reenvio por período afetaria — só conta, não envia."""
    tipo_resolvido = _resolver_tipo_reenvio(tipo)
    if not data_inicio and not data_fim:
        raise HTTPException(
            status_code=422,
            detail="Informe ao menos uma data para o reenvio por período.",
        )
    total = _query_lote_reenviar(
        db, tipo_resolvido, data_inicio, data_fim, industria_nome, status_erp
    ).count()
    limite = _limite_reenvio(db)
    return ReenvioPreview(total=total, limite=limite, excede=total > limite)


@router.post("/lote/reenviar", response_model=LoteResultado)
def reenviar_lote(
    body: ReenviarLoteBody,
    db: Session = Depends(get_db),
    current_user=Depends(_OPERACIONAL),
):
    """Reenvia arquivos já gerados, por seleção (`ids`) ou por período.

    Reenvio é entrega, não processamento: o conteúdo é o mesmo arquivo que a
    indústria recebeu antes (lido do caminho gravado em `arquivo`), e o status
    do pedido não é alterado. Cada item é isolado pelo `_lote_executar` — um
    pedido sem o arquivo em disco falha sozinho, sem derrubar o lote.

    Em ambos os modos o reenvio é de UM tipo — retorno, espelho ou cancelamento.
    Não existe disparo de "todos": quem reenvia declara o que vai sair.
    """
    tipo = _resolver_tipo_reenvio(body.tipo)

    por_periodo = not body.ids
    if por_periodo:
        if not body.data_inicio and not body.data_fim:
            raise HTTPException(
                status_code=422,
                detail="Informe os pedidos (ids) ou ao menos uma data para o reenvio por período.",
            )
        q = _query_lote_reenviar(
            db, tipo, body.data_inicio, body.data_fim, body.industria_nome, body.status_erp
        )
        total = q.count()
        limite = _limite_reenvio(db)
        if total > limite:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"O período selecionado tem {total} pedidos, acima do limite de {limite} "
                    f"por reenvio. Estreite o período ou ajuste o limitador na tela de Parametrização."
                ),
            )
        pedidos = q.options(joinedload(Pedido.industria), selectinload(Pedido.arquivos)).all()
        if not pedidos:
            raise HTTPException(
                status_code=404,
                detail=f"Nenhum pedido com arquivo de {tipo} gerado no período selecionado.",
            )
    else:
        pedidos = (
            db.query(Pedido)
            .options(joinedload(Pedido.industria), selectinload(Pedido.arquivos))
            .filter(Pedido.id.in_(body.ids))
            .all()
        )
        if not pedidos:
            raise HTTPException(status_code=404, detail="Nenhum pedido encontrado para os ids informados.")

    return _lote_executar(
        pedidos,
        lambda p, uid: operacoes.executar_reenviar_arquivo(p, tipo, uid),
        current_user.id,
    )


@router.get("/lote/transmitir/preview", response_model=LotePreview)
def preview_lote_transmitir(
    apenas_sem_ocorrencia: bool = Query(False),
    db: Session = Depends(get_db),
    _user=Depends(_OPERACIONAL),
):
    """Quantos pedidos a transmissão em lote afetaria — só conta."""
    return LotePreview(total=_query_lote_transmitir(db, apenas_sem_ocorrencia).count())
