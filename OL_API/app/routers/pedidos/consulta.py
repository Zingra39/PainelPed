"""Listagens paginadas: pedidos, Triagem (confecção), Rastreamento e Histórico."""
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models import Pedido
from app.schemas.pedido import (
    PaginatedPedidos,
    PaginatedPedidosConfeccao,
    PaginatedPedidosRastreamento,
    PedidoListItem,
    PedidoRastreamentoItem,
)
from app.services import operacoes
from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.enums.tipo_status_oper import TipoStatusOper

from ._comum import (
    _TODOS,
    _analise_campos,
    _conta_ocorrencias,
    _envio_somente_pronto,
    _filtrar_analisado,
    _filtrar_busca,
    _selo_analisado,
)
from ._rastreamento import _filtrar_historico, _montar_status_arquivos, _query_rastreamento

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


@router.get("", response_model=PaginatedPedidos)
def listar_pedidos(
    numero_pedido_ol: Optional[str] = Query(None),
    cnpj_cliente: Optional[str] = Query(None),
    status_operacional: Optional[str] = Query(None),
    status_erp: Optional[str] = Query(None),
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    id_industria: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    try:
        q = db.query(Pedido).options(joinedload(Pedido.industria), joinedload(Pedido.usuario_analise), joinedload(Pedido.usuario_analisou))

        if numero_pedido_ol:
            q = q.filter(Pedido.numero_pedido_ol.ilike(f"%{numero_pedido_ol}%"))
        if cnpj_cliente:
            q = q.filter(Pedido.cnpj_cliente.ilike(f"%{cnpj_cliente}%"))
        if status_operacional:
            q = q.filter(Pedido.status_operacional == status_operacional)
        if status_erp:
            q = q.filter(Pedido.status_erp == status_erp)
        if id_industria:
            q = q.filter(Pedido.id_industria == id_industria)
        if data_inicio:
            q = q.filter(Pedido.data_pedido >= datetime.combine(data_inicio, datetime.min.time()))
        if data_fim:
            q = q.filter(Pedido.data_pedido <= datetime.combine(data_fim, datetime.max.time()))

        total = q.count()
        status_order = case(
            (Pedido.status_operacional == TipoStatusOper.VERIFICAR.value, 0),
            else_=1,
        )
        pedidos = q.order_by(status_order, Pedido.data_pedido.desc()).offset((page - 1) * size).limit(size).all()

        # Contagem de ocorrências por pedido
        total_map, abertas_map = _conta_ocorrencias(db, pedidos)

        items = [
            PedidoListItem(
                id=cast(int,p.id),
                numero_pedido_ol=cast(str,p.numero_pedido_ol),
                cnpj_cliente=cast(str,p.cnpj_cliente),
                condicao=cast(str,p.condicao),
                status_operacional=cast(str,p.status_operacional),
                status_erp=cast(str,p.status_erp),
                valor_total=cast(Decimal,p.valor_total),
                data_pedido=cast(datetime,p.data_pedido),
                industria_nome=p.industria.nome if p.industria else None,
                total_ocorrencias=total_map.get(p.numero_pedido_ol, 0),
                total_ocorrencias_abertas=abertas_map.get(p.numero_pedido_ol, 0),
                **_analise_campos(p),
            )
            for p in pedidos
        ]

        return PaginatedPedidos(items=items, total=total, page=page, size=size, pages=math.ceil(total / size) if total else 1)
    except ErroConexaoBanco:
        raise
    except Exception as err:
        return {"error": str(err)}


@router.get("/confeccao", response_model=PaginatedPedidosConfeccao)
def listar_confeccao(
    busca: Optional[str] = Query(None, description="Palavras-chave: nº do pedido, CNPJ, nome do arquivo ou indústria"),
    numero_pedido_ol: Optional[str] = Query(None),
    cnpj_cliente: Optional[str] = Query(None),
    nome_arquivo: Optional[str] = Query(None),
    status_operacional: Optional[str] = Query(None),
    analisado: Optional[bool] = Query(None, description="true = só já analisados; false = só nunca analisados"),
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    """Pedidos ainda não transmitidos (em processo de confecção)."""
    q = (
        db.query(Pedido)
        .options(joinedload(Pedido.industria), joinedload(Pedido.usuario_analise), joinedload(Pedido.usuario_analisou))
        .filter(Pedido.status_erp == TipoStatusErp.NAO_TRANSMITIDO.value)
    )

    q = _filtrar_busca(q, busca)
    if numero_pedido_ol:
        q = q.filter(Pedido.numero_pedido_ol.ilike(f"%{numero_pedido_ol}%"))
    if cnpj_cliente:
        q = q.filter(Pedido.cnpj_cliente.ilike(f"%{cnpj_cliente}%"))
    if nome_arquivo:
        # Busca exata: nome_arquivo é único por pedido (ver Pedido.nome_arquivo),
        # então usamos "==" em vez de ilike — usa o índice único e evita scan.
        q = q.filter(Pedido.nome_arquivo == nome_arquivo.strip())
    if status_operacional:
        q = q.filter(Pedido.status_operacional == status_operacional)
    q = _filtrar_analisado(q, analisado)
    if data_inicio:
        q = q.filter(Pedido.data_pedido >= datetime.combine(data_inicio, datetime.min.time()))
    if data_fim:
        q = q.filter(Pedido.data_pedido <= datetime.combine(data_fim, datetime.max.time()))

    contagem_por_status = {
        status: total
        for status, total in q.with_entities(
            Pedido.status_operacional, func.count()
        ).group_by(Pedido.status_operacional).all()
    }

    total = q.count()
    pedidos = q.order_by(Pedido.data_pedido.asc()).offset((page - 1) * size).limit(size).all()

    total_map, abertas_map = _conta_ocorrencias(db, pedidos)

    items = [
        PedidoListItem(
            id=cast(int,p.id),
            numero_pedido_ol=cast(str,p.numero_pedido_ol),
            cnpj_cliente=cast(str,p.cnpj_cliente),
            condicao=cast(str,p.condicao),
            status_operacional=cast(str,p.status_operacional),
            status_erp=cast(str,p.status_erp),
            valor_total=cast(Decimal,p.valor_total),
            data_pedido=cast(datetime,p.data_pedido),
            industria_nome=p.industria.nome if p.industria else None,
            total_ocorrencias=total_map.get(p.numero_pedido_ol, 0),
            total_ocorrencias_abertas=abertas_map.get(p.numero_pedido_ol, 0),
            **_analise_campos(p),
        )
        for p in pedidos
    ]

    return PaginatedPedidosConfeccao(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 1,
        contagem_por_status=contagem_por_status,
        envio_somente_pronto=_envio_somente_pronto(db),
    )


@router.get("/rastreamento", response_model=PaginatedPedidosRastreamento)
def listar_rastreamento(
    busca: Optional[str] = Query(None, description="Palavras-chave: nº do pedido, CNPJ, nome do arquivo ou indústria"),
    numero_pedido_ol: Optional[str] = Query(None),
    cnpj_cliente: Optional[str] = Query(None),
    nome_arquivo: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    """Pedidos já transmitidos, com o status dos arquivos Retorno/Espelho/Cancelamento.

    Paginação no banco (COUNT + LIMIT/OFFSET), filtro de status inclusive —
    antes a tela carregava TODOS os pedidos em andamento, com seus arquivos,
    para filtrar e fatiar a página em Python."""
    q = _query_rastreamento(
        db, numero_pedido_ol, cnpj_cliente, data_inicio, data_fim,
        nome_arquivo=nome_arquivo, busca=busca, status=status,
    )
    total = q.count()
    pedidos = q.order_by(Pedido.atualizado_em.desc(), Pedido.id.desc()).offset((page - 1) * size).limit(size).all()

    total_map, abertas_map = _conta_ocorrencias(db, pedidos)

    pagina: list[PedidoRastreamentoItem] = []
    for p in pedidos:
        retorno_status, espelho_status, cancelamento_status, falha_geral = _montar_status_arquivos(p)
        pagina.append(
            PedidoRastreamentoItem(
                id=cast(int, p.id),
                numero_pedido_ol=cast(str, p.numero_pedido_ol),
                cnpj_cliente=cast(str, p.cnpj_cliente),
                condicao=cast(str, p.condicao),
                status_operacional=cast(str, p.status_operacional),
                status_erp=cast(str, p.status_erp),
                valor_total=cast(Decimal, p.valor_total),
                data_pedido=cast(datetime, p.data_pedido),
                industria_nome=p.industria.nome if p.industria else None,
                total_ocorrencias=total_map.get(p.numero_pedido_ol, 0),
                total_ocorrencias_abertas=abertas_map.get(p.numero_pedido_ol, 0),
                retorno_status=retorno_status,
                espelho_status=espelho_status,
                cancelamento_status=cancelamento_status,
                falha_geral=falha_geral,
                retorno_manual_liberado=operacoes.retorno_manual_liberado_por_atraso(p),
                **operacoes.acoes_de_geracao_manual(p),
                **_selo_analisado(p),
            )
        )

    return PaginatedPedidosRastreamento(
        items=pagina,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 1,
    )


@router.get("/historico", response_model=PaginatedPedidosRastreamento)
def listar_historico(
    busca: Optional[str] = Query(None, description="Palavras-chave: nº do pedido, CNPJ, nome do arquivo ou indústria"),
    numero_pedido_ol: Optional[str] = Query(None),
    cnpj_cliente: Optional[str] = Query(None),
    nome_arquivo: Optional[str] = Query(None),
    industria_nome: Optional[str] = Query(None),
    status_erp: Optional[str] = Query(None),
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    """Pedidos com o fluxo encerrado — status_erp igual a "Processo Concluido"
    (Retorno + Espelho gerados, pedido faturado) ou "Pedido Cancelado"
    (Retorno + Cancelamento gerados). Assim que um pedido chega em um desses
    dois estágios, `_filtrar_rastreamento` o exclui da tela de Rastreamento —
    ele só volta a aparecer aqui."""
    q = _filtrar_historico(db, numero_pedido_ol, cnpj_cliente, industria_nome, status_erp, data_inicio, data_fim, nome_arquivo=nome_arquivo, busca=busca)

    total = q.count()
    pedidos = q.order_by(Pedido.atualizado_em.desc()).offset((page - 1) * size).limit(size).all()

    total_map, abertas_map = _conta_ocorrencias(db, pedidos)

    items: list[PedidoRastreamentoItem] = []
    for p in pedidos:
        retorno_status, espelho_status, cancelamento_status, falha_geral = _montar_status_arquivos(p)
        items.append(
            PedidoRastreamentoItem(
                id=cast(int, p.id),
                numero_pedido_ol=cast(str, p.numero_pedido_ol),
                cnpj_cliente=cast(str, p.cnpj_cliente),
                condicao=cast(str, p.condicao),
                status_operacional=cast(str, p.status_operacional),
                status_erp=cast(str, p.status_erp),
                valor_total=cast(Decimal, p.valor_total),
                data_pedido=cast(datetime, p.data_pedido),
                industria_nome=p.industria.nome if p.industria else None,
                total_ocorrencias=total_map.get(p.numero_pedido_ol, 0),
                total_ocorrencias_abertas=abertas_map.get(p.numero_pedido_ol, 0),
                retorno_status=retorno_status,
                espelho_status=espelho_status,
                cancelamento_status=cancelamento_status,
                falha_geral=falha_geral,
                motivo_cancelamento=cast(str, p.motivo_cancelamento),
                **_selo_analisado(p),
            )
        )

    return PaginatedPedidosRastreamento(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 1,
    )
