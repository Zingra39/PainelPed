from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class ParametroResponse(BaseModel):
    id: int
    chave: str
    valor: Optional[str]
    descricao: Optional[str]
    atualizado_em: Optional[datetime]
    # Nome de quem alterou por último — não o id, a tela de parametrização
    # não precisa (nem deve) resolver isso sozinha.
    atualizado_por: Optional[str] = None

    model_config = {"from_attributes": True}


class ParametroUpdate(BaseModel):
    # Vazio só é aceito pelos parâmetros que permitem "não configurado" — a
    # regra por chave fica em app/routers/parametros.py (normalizar_valor).
    valor: str

    @field_validator("valor")
    @classmethod
    def _apara(cls, v: str) -> str:
        return v.strip()


class PendenciaConfiguracao(BaseModel):
    """Configuração obrigatória ausente — vira alerta para todos os usuários."""
    chave: str
    titulo: str
    mensagem: str
