import math
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_perfis
from app.models import Arquivo, Pedido
from app.schemas.pedido import ArquivoResumo
from sqlalchemy.orm import joinedload
from pydantic import BaseModel

# Mesma resolução de servicos.py e services/operacoes/conversao.py: OL_SERVICES_PATH
# tem prioridade; sem ela, cai na pasta irmã OL_Services (layout de dev).
_OL_SERVICES_BASE = os.getenv("OL_SERVICES_PATH", os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "OL_Services")
))

router = APIRouter(prefix="/arquivos", tags=["Arquivos"])

_TODOS = require_perfis("Administrador", "Operador Logístico", "Gerente Comercial")
_OPERACIONAL = require_perfis("Administrador", "Operador Logístico")


class ArquivosPaginados(BaseModel):
    items: list[ArquivoResumo]
    total: int
    page: int
    size: int
    pages: int


@router.get("", response_model=ArquivosPaginados)
def listar_arquivos(
    numero_pedido_ol: Optional[str] = Query(None),
    nome: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    situacao: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(_TODOS),
):
    q = db.query(Arquivo).options(joinedload(Arquivo.pedido))

    if numero_pedido_ol:
        q = q.filter(Arquivo.numero_pedido_ol.ilike(f"%{numero_pedido_ol}%"))
    if nome:
        q = q.filter(Arquivo.nome.ilike(f"%{nome}%"))
    if tipo:
        q = q.filter(Arquivo.tipo == tipo)
    if situacao:
        q = q.filter(Arquivo.situacao == situacao)

    total = q.count()
    items = q.order_by(Arquivo.criado_em.desc()).offset((page - 1) * size).limit(size).all()

    return ArquivosPaginados(
        items=[
            ArquivoResumo(
                id=a.id,
                id_pedido=a.pedido.id if a.pedido else None,
                numero_pedido_ol=a.numero_pedido_ol,
                nome=a.nome,
                tipo=a.tipo,
                hash_md5=a.hash_md5,
                situacao=a.situacao,
                criado_em=a.criado_em,
            )
            for a in items
        ],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 1,
    )


@router.get("/{id}/download")
def download_arquivo(
    id: int,
    db: Session = Depends(get_db),
    _user=Depends(_OPERACIONAL),
):
    arquivo = db.query(Arquivo).filter(Arquivo.id == id).first()
    if not arquivo:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    caminho = arquivo.caminho
    if caminho and not os.path.isabs(caminho):
        caminho = os.path.join(_OL_SERVICES_BASE, caminho)

    if (not caminho or not os.path.exists(caminho)) and arquivo.tipo == 'pedido' and arquivo.nome:
        pedido = (
            db.query(Pedido)
            .options(joinedload(Pedido.industria))
            .filter(Pedido.numero_pedido_ol == arquivo.numero_pedido_ol)
            .first()
        )
        industria_db = pedido.industria if pedido else None
        if industria_db:
            pasta_backup = industria_db.pasta_backup_pedido or "ERP/BACKUP"
            if not os.path.isabs(pasta_backup):
                pasta_backup = os.path.join(_OL_SERVICES_BASE, pasta_backup)
            caminho = os.path.join(pasta_backup, arquivo.nome)

    if not caminho or not os.path.exists(caminho):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no servidor de arquivos.")

    return FileResponse(
        path=caminho,
        filename=arquivo.nome,
        media_type="text/plain",
    )
