from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ServicoStatus(BaseModel):
    id: int
    nome: str
    status: Optional[str]
    ultimo_heartbeat: Optional[datetime]
    mensagem: Optional[str]
    timeout_minutos: int
    online: bool

    model_config = {"from_attributes": True}
