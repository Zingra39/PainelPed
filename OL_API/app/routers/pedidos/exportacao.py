"""Exportação xlsx das listagens de Triagem, Rastreamento e Histórico."""
import io
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, cast

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models import Pedido, PedidoOcorrencia
from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.models.enums.tipo_status_erp import TipoStatusErp

from ._comum import (
    _TODOS,
    _filtrar_analisado,
    _filtrar_busca,
    _selo_analisado,
    _severidade_conta_como_pendencia,
)
from ._rastreamento import _filtrar_historico, _filtrar_rastreamento, _montar_status_arquivos

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


def _selo_colunas_xlsx(p: Pedido) -> dict:
    """Colunas do selo "Analisado" nas planilhas (vazias se nunca analisado)."""
    selo = _selo_analisado(p)
    return {"Analisado Por": selo["analisado_por"], "Analisado Em": selo["analisado_em"]}


def _gerar_xlsx_response(linhas: list[dict], nome_arquivo: str) -> StreamingResponse:
    df = pd.DataFrame(linhas)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Pedidos")
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.get("/confeccao/export")
def exportar_confeccao(
    busca: Optional[str] = Query(None),
    numero_pedido_ol: Optional[str] = Query(None),
    cnpj_cliente: Optional[str] = Query(None),
    nome_arquivo: Optional[str] = Query(None),
    status_operacional: Optional[str] = Query(None),
    analisado: Optional[bool] = Query(None, description="true = só já analisados; false = só nunca analisados"),
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    try:
        q = (
            db.query(Pedido)
            .options(joinedload(Pedido.industria), joinedload(Pedido.usuario_analisou))
            .filter(Pedido.status_erp == TipoStatusErp.NAO_TRANSMITIDO.value)
        )
        q = _filtrar_busca(q, busca)
        if numero_pedido_ol:
            q = q.filter(Pedido.numero_pedido_ol.ilike(f"%{numero_pedido_ol}%"))
        if cnpj_cliente:
            q = q.filter(Pedido.cnpj_cliente.ilike(f"%{cnpj_cliente}%"))
        if nome_arquivo:
            q = q.filter(Pedido.nome_arquivo == nome_arquivo.strip())
        if status_operacional:
            q = q.filter(Pedido.status_operacional == status_operacional)
        q = _filtrar_analisado(q, analisado)
        if data_inicio:
            q = q.filter(Pedido.data_pedido >= datetime.combine(data_inicio, datetime.min.time()))
        if data_fim:
            q = q.filter(Pedido.data_pedido <= datetime.combine(data_fim, datetime.max.time()))
    
        pedidos = q.order_by(Pedido.data_pedido.asc()).all()
    
        nums = [p.numero_pedido_ol for p in pedidos]
        abertas_oc = (
            db.query(PedidoOcorrencia.numero_pedido_ol, func.count().label("total"))
            .filter(
                PedidoOcorrencia.numero_pedido_ol.in_(nums),
                PedidoOcorrencia.resolvido == False,  # noqa: E712
                _severidade_conta_como_pendencia(),
            )
            .group_by(PedidoOcorrencia.numero_pedido_ol)
            .all()
        ) if nums else []
        abertas_map = {r.numero_pedido_ol: r.total for r in abertas_oc}
    
        linhas = [
            {
                "Pedido OL": p.numero_pedido_ol,
                "CNPJ Cliente": p.cnpj_cliente,
                "Indústria": p.industria.nome if p.industria else None,
                "Data Pedido": p.data_pedido,
                "Status Operacional": p.status_operacional,
                "Status ERP": p.status_erp,
                "Valor Total": float(cast(Decimal, p.valor_total)) if p.valor_total is not None else None,
                "Ocorrências Abertas": abertas_map.get(p.numero_pedido_ol, 0),
                **_selo_colunas_xlsx(p),
            }
            for p in pedidos
        ]
        return _gerar_xlsx_response(linhas, "confeccao.xlsx")
    except ErroConexaoBanco:
        raise
    except Exception as err:
        return {"error": str(err)}


@router.get("/rastreamento/export")
def exportar_rastreamento(
    busca: Optional[str] = Query(None),
    numero_pedido_ol: Optional[str] = Query(None),
    cnpj_cliente: Optional[str] = Query(None),
    nome_arquivo: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    try:
        pedidos = _filtrar_rastreamento(
            db, numero_pedido_ol, cnpj_cliente, data_inicio, data_fim,
            nome_arquivo=nome_arquivo, busca=busca, status=status,
        )

        linhas = []
        for p in pedidos:
            retorno_status, espelho_status, cancelamento_status, _falha = _montar_status_arquivos(p)
            linhas.append({
                "Pedido OL": p.numero_pedido_ol,
                "CNPJ Cliente": p.cnpj_cliente,
                "Indústria": p.industria.nome if p.industria else None,
                "Data Pedido": p.data_pedido,
                "Status Operacional": p.status_operacional,
                "Status ERP": p.status_erp,
                "Valor Total": float(cast(Decimal, p.valor_total)) if p.valor_total is not None else None,
                "Retorno": retorno_status,
                "Espelho": espelho_status,
                "Cancelamento": cancelamento_status,
                **_selo_colunas_xlsx(p),
            })
        return _gerar_xlsx_response(linhas, "rastreamento.xlsx")
    except ErroConexaoBanco:
        raise
    except Exception as err:
        return {"error": str(err)}


@router.get("/historico/export")
def exportar_historico(
    data_inicio: date = Query(..., description="Obrigatório: início do período (data_pedido)"),
    data_fim: date = Query(..., description="Obrigatório: fim do período (data_pedido)"),
    busca: Optional[str] = Query(None),
    numero_pedido_ol: Optional[str] = Query(None),
    cnpj_cliente: Optional[str] = Query(None),
    nome_arquivo: Optional[str] = Query(None),
    industria_nome: Optional[str] = Query(None),
    status_erp: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    """Planilha dos pedidos encerrados de um período.

    O período é OBRIGATÓRIO (ao contrário dos exports de Confecção e
    Rastreamento): o Histórico acumula tudo que já encerrou, então um export
    sem recorte cresce sem teto e o arquivo deixa de ser útil — e caro de
    gerar. Os demais filtros são os mesmos da listagem, via
    `_filtrar_historico`, para a planilha bater linha a linha com a tela."""
    if data_fim < data_inicio:
        raise HTTPException(
            status_code=422,
            detail="A data final do período não pode ser anterior à data inicial.",
        )

    try:
        q = _filtrar_historico(
            db, numero_pedido_ol, cnpj_cliente, industria_nome,
            status_erp, data_inicio, data_fim, nome_arquivo=nome_arquivo, busca=busca,
        )
        pedidos = q.order_by(Pedido.data_pedido.asc()).all()

        linhas = []
        for p in pedidos:
            retorno_status, espelho_status, cancelamento_status, _falha = _montar_status_arquivos(p)
            linhas.append({
                "Pedido OL": p.numero_pedido_ol,
                "CNPJ Cliente": p.cnpj_cliente,
                "Indústria": p.industria.nome if p.industria else None,
                "Data Pedido": p.data_pedido,
                "Situação": p.status_erp,
                "Valor Total": float(cast(Decimal, p.valor_total)) if p.valor_total is not None else None,
                "Retorno": retorno_status,
                "Espelho": espelho_status,
                "Cancelamento": cancelamento_status,
                "Motivo do Cancelamento": p.motivo_cancelamento,
                **_selo_colunas_xlsx(p),
            })
        return _gerar_xlsx_response(linhas, "historico.xlsx")
    except HTTPException:
        raise
    except ErroConexaoBanco:
        raise
    except Exception as err:
        return {"error": str(err)}
