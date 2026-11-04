import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_perfis
from app.core.security import hash_password
from app.models import Perfil, PedidoHistorico, Usuario
from app.schemas.usuario import (
    PaginatedUsuarios,
    PerfilSchema,
    UsuarioCreate,
    UsuarioResponse,
    UsuarioUpdate,
)

router = APIRouter(prefix="/usuarios", tags=["Usuários"])

_ADMIN = require_perfis("Administrador")


def _to_response(u: Usuario) -> UsuarioResponse:
    return UsuarioResponse(
        id=u.id,
        nome=u.nome,
        email=u.email,
        ativo=bool(u.ativo),
        id_perfil=u.id_perfil,
        perfil_nome=u.perfil.nome if u.perfil else None,
        ultimo_acesso=u.ultimo_acesso,
        criado_em=u.criado_em,
    )


# ----------------------------------------------------------------------- perfis
@router.get("/perfis", response_model=list[PerfilSchema])
def listar_perfis(db: Session = Depends(get_db), _user=Depends(_ADMIN)):
    return [PerfilSchema(id=p.id, nome=p.nome, permissoes=p.permissoes) for p in db.query(Perfil).all()]


# ----------------------------------------------------------------------- listagem
@router.get("", response_model=PaginatedUsuarios)
def listar_usuarios(
    nome: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    ativo: Optional[bool] = Query(None),
    id_perfil: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(_ADMIN),
):
    from sqlalchemy.orm import joinedload

    q = db.query(Usuario).options(joinedload(Usuario.perfil))

    if nome:
        q = q.filter(Usuario.nome.ilike(f"%{nome}%"))
    if email:
        q = q.filter(Usuario.email.ilike(f"%{email}%"))
    if ativo is not None:
        q = q.filter(Usuario.ativo == ativo)
    if id_perfil:
        q = q.filter(Usuario.id_perfil == id_perfil)

    total = q.count()
    usuarios = q.order_by(Usuario.nome).offset((page - 1) * size).limit(size).all()

    return PaginatedUsuarios(
        items=[_to_response(u) for u in usuarios],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 1,
    )


# ----------------------------------------------------------------------- criar
@router.post("", response_model=UsuarioResponse, status_code=201)
def criar_usuario(body: UsuarioCreate, db: Session = Depends(get_db), _user=Depends(_ADMIN)):
    if db.query(Usuario).filter(Usuario.email == body.email).first():
        raise HTTPException(status_code=409, detail="E-mail já cadastrado.")

    perfil = db.query(Perfil).filter(Perfil.id == body.id_perfil).first()
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")

    novo = Usuario(
        nome=body.nome,
        email=body.email,
        senha_hash=hash_password(body.senha),
        id_perfil=body.id_perfil,
        ativo=True,
        criado_em=datetime.now(timezone.utc),
        atualizado_em=datetime.now(timezone.utc),
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return _to_response(novo)


# ----------------------------------------------------------------------- detalhe
@router.get("/{id}", response_model=UsuarioResponse)
def detalhe_usuario(id: int, db: Session = Depends(get_db), _user=Depends(_ADMIN)):
    from sqlalchemy.orm import joinedload

    u = db.query(Usuario).options(joinedload(Usuario.perfil)).filter(Usuario.id == id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return _to_response(u)


# ----------------------------------------------------------------------- atualizar
@router.put("/{id}", response_model=UsuarioResponse)
def atualizar_usuario(
    id: int,
    body: UsuarioUpdate,
    db: Session = Depends(get_db),
    _user=Depends(_ADMIN),
):
    from sqlalchemy.orm import joinedload

    u = db.query(Usuario).options(joinedload(Usuario.perfil)).filter(Usuario.id == id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    if body.email and body.email != u.email:
        if db.query(Usuario).filter(Usuario.email == body.email, Usuario.id != id).first():
            raise HTTPException(status_code=409, detail="E-mail já utilizado por outro usuário.")
        u.email = body.email

    if body.nome is not None:
        u.nome = body.nome
    if body.senha:
        u.senha_hash = hash_password(body.senha)
    if body.id_perfil is not None:
        if not db.query(Perfil).filter(Perfil.id == body.id_perfil).first():
            raise HTTPException(status_code=404, detail="Perfil não encontrado.")
        u.id_perfil = body.id_perfil
    if body.ativo is not None:
        u.ativo = body.ativo

    u.atualizado_em = datetime.now(timezone.utc)
    db.commit()
    db.refresh(u)
    return _to_response(u)


# ----------------------------------------------------------------------- desativar
@router.delete("/{id}", status_code=204)
def desativar_usuario(id: int, db: Session = Depends(get_db), current_user=Depends(_ADMIN)):
    u = db.query(Usuario).filter(Usuario.id == id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if u.id == current_user.id:
        raise HTTPException(status_code=400, detail="Não é possível desativar o próprio usuário.")
    u.ativo = False
    u.atualizado_em = datetime.now(timezone.utc)
    db.commit()


# ----------------------------------------------------------------------- excluir (definitivo)
@router.delete("/{id}/permanente", status_code=204)
def excluir_usuario_permanente(id: int, db: Session = Depends(get_db), current_user=Depends(_ADMIN)):
    """Remove o usuário definitivamente. Diferente de `desativar_usuario`
    (que só marca ativo=False e é reversível), esta ação apaga a linha da
    tabela usuario e não pode ser desfeita."""
    u = db.query(Usuario).filter(Usuario.id == id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if u.id == current_user.id:
        raise HTTPException(status_code=400, detail="Não é possível excluir o próprio usuário.")

    # A FK de pedido_historico pra usuario não tem ON DELETE definido (RESTRICT
    # no MySQL), então o DELETE falharia pra qualquer usuário com histórico.
    # Preservamos os registros de auditoria e só desvinculamos o autor
    # (id_usuario vira NULL — mesmo tratamento já usado pra ações automáticas).
    db.query(PedidoHistorico).filter(PedidoHistorico.id_usuario == id).update(
        {PedidoHistorico.id_usuario: None}
    )
    db.delete(u)
    db.commit()
