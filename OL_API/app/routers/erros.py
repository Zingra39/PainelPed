from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_perfis
from app.models import Erros

router = APIRouter(prefix="/erros", tags=["Erros"])

_TODOS = require_perfis("Administrador", "Operador Logístico", "Gerente Comercial")


class ErroItem(BaseModel):
    id: int
    codigo_erp: Optional[int]
    descricao: Optional[str]

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ErroItem])
def listar_erros(
    descricao: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    """Catálogo de erros conhecidos do sistema (tabela 'erros')."""
    q = db.query(Erros)
    if descricao:
        q = q.filter(Erros.descricao.ilike(f"%{descricao}%"))
    return q.order_by(Erros.codigo_erp.asc()).all()
