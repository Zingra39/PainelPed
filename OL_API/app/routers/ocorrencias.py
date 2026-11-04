from datetime import datetime
import math
from typing import Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import require_perfis
from app.models import PedidoOcorrencia
from app.schemas.pedido import OcorrenciaResumo

router = APIRouter(prefix="/ocorrencias", tags=["Ocorrências"])

_TODOS = require_perfis("Administrador", "Operador Logístico", "Gerente Comercial")


class PaginatedOcorrencias:
    pass


from pydantic import BaseModel


class OcorrenciasPaginadas(BaseModel):
    items: list[OcorrenciaResumo]
    total: int
    page: int
    size: int
    pages: int


@router.get("", response_model=OcorrenciasPaginadas)
def listar_ocorrencias(
    numero_pedido_ol: Optional[str] = Query(None),
    severidade: Optional[str] = Query(None),
    resolvido: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    q = db.query(PedidoOcorrencia).options(joinedload(PedidoOcorrencia.pedido))

    if numero_pedido_ol:
        q = q.filter(PedidoOcorrencia.numero_pedido_ol.ilike(f"%{numero_pedido_ol}%"))
    if severidade:
        q = q.filter(PedidoOcorrencia.severidade == severidade)
    if resolvido is not None:
        q = q.filter(PedidoOcorrencia.resolvido == resolvido)

    total = q.count()
    items = q.order_by(PedidoOcorrencia.criado_em.desc()).offset((page - 1) * size).limit(size).all()

    return OcorrenciasPaginadas(
        items=[
            OcorrenciaResumo(
                id=cast(int, oc.id),
                id_pedido=oc.pedido.id if oc.pedido else None,
                numero_pedido_ol=cast(str, oc.numero_pedido_ol),
                severidade=cast(str, oc.severidade),
                codigo=cast(str, oc.codigo),
                descricao=cast(str, oc.descricao),
                resolvido=bool(oc.resolvido),
                criado_em=cast(datetime, oc.criado_em),
            )
            for oc in items
        ],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 1,
    )


@router.get("/{id}", response_model=OcorrenciaResumo)
def detalhe_ocorrencia(
    id: int,
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    oc = (
        db.query(PedidoOcorrencia)
        .options(joinedload(PedidoOcorrencia.pedido))
        .filter(PedidoOcorrencia.id == id)
        .first()
    )
    if not oc:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada.")
    return OcorrenciaResumo(
        id=cast(int, oc.id),
        id_pedido=oc.pedido.id if oc.pedido else None,
        numero_pedido_ol=cast(str, oc.numero_pedido_ol),
        severidade=cast(str, oc.severidade),
        codigo=cast(str, oc.codigo),
        descricao=cast(str, oc.descricao),
        resolvido=bool(oc.resolvido),
        criado_em=cast(datetime, oc.criado_em),
    )
