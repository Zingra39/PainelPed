from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models import Usuario
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse, UserMe

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = (
        db.query(Usuario)
        .options(joinedload(Usuario.perfil))
        .filter(Usuario.email == body.email, Usuario.ativo == True)
        .first()
    )

    if not user or not verify_password(body.senha, user.senha_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas.")

    user.ultimo_acesso = datetime.now(timezone.utc)
    db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token, "refresh")
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido ou expirado.")

    user = db.query(Usuario).filter(Usuario.id == int(payload["sub"]), Usuario.ativo == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado.")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserMe)
def me(current_user: Usuario = Depends(get_current_user)):
    return UserMe(
        id=current_user.id,
        nome=current_user.nome,
        email=current_user.email,
        perfil=current_user.perfil.nome if current_user.perfil else "",
        ativo=current_user.ativo,
    )
