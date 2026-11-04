from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class PerfilSchema(BaseModel):
    id: int
    nome: str
    permissoes: Optional[dict | list] = None

    model_config = {"from_attributes": True}


class UsuarioCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    id_perfil: int


class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    senha: Optional[str] = None
    id_perfil: Optional[int] = None
    ativo: Optional[bool] = None


class UsuarioResponse(BaseModel):
    id: int
    nome: Optional[str]
    email: Optional[str]
    ativo: bool
    id_perfil: Optional[int]
    perfil_nome: Optional[str]
    ultimo_acesso: Optional[datetime]
    criado_em: Optional[datetime]

    model_config = {"from_attributes": True}


class PaginatedUsuarios(BaseModel):
    items: list[UsuarioResponse]
    total: int
    page: int
    size: int
    pages: int
