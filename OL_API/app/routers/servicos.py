import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_perfis, require_service_key
from app.models import ServicoMonitorado
from app.schemas.servico import ServicoStatus

router = APIRouter(prefix="/servicos", tags=["Serviços"])

_OL_SERVICES_BASE = os.getenv("OL_SERVICES_PATH", os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "OL_Services")
))

_ADMIN = require_perfis("Administrador")

_SERVICOS_PERMITIDOS = frozenset({
    "cancelados",
    "retornos",
    "espelhos",
    "importa_pedidos",
    "coleta_pedidos_ftp",
    "envio_estoque",
})


class HeartbeatPayload(BaseModel):
    status: Optional[str] = "OK"
    mensagem: Optional[str] = None


def _is_online(servico: ServicoMonitorado) -> bool:
    if not servico.ultimo_heartbeat:
        return False
    limite = datetime.now(timezone.utc) - timedelta(minutes=servico.timeout_minutos)
    ultimo = servico.ultimo_heartbeat
    if ultimo.tzinfo is None:
        from datetime import timezone as tz
        ultimo = ultimo.replace(tzinfo=tz.utc)
    return ultimo >= limite


@router.get("", response_model=list[ServicoStatus])
def listar_servicos(db: Session = Depends(get_db), _user=Depends(_ADMIN)):
    servicos = db.query(ServicoMonitorado).order_by(ServicoMonitorado.nome).all()
    return [
        ServicoStatus(
            id=s.id,
            nome=s.nome,
            status=s.status,
            ultimo_heartbeat=s.ultimo_heartbeat,
            mensagem=s.mensagem,
            timeout_minutos=s.timeout_minutos or 10,
            online=_is_online(s),
        )
        for s in servicos
    ]


@router.post("/{nome}/executar", status_code=202)
def executar_servico(nome: str, db: Session = Depends(get_db), _user=Depends(_ADMIN)):
    if nome not in _SERVICOS_PERMITIDOS:
        raise HTTPException(status_code=400, detail=f"Serviço '{nome}' não é permitido.")
    servico = db.query(ServicoMonitorado).filter(ServicoMonitorado.nome == nome).first()
    if not servico:
        raise HTTPException(status_code=404, detail=f"Serviço '{nome}' não encontrado.")
    script = os.path.join(_OL_SERVICES_BASE, f"{nome}.py")
    if not os.path.exists(script):
        raise HTTPException(
            status_code=422,
            detail=f"Script de execução '{nome}.py' não encontrado em OL_Services/.",
        )
    subprocess.Popen([sys.executable, script], cwd=_OL_SERVICES_BASE)
    return {"mensagem": f"Execução do serviço '{nome}' iniciada."}


@router.post("/{nome}/heartbeat", status_code=204)
def heartbeat(
    nome: str,
    payload: HeartbeatPayload = None,
    db: Session = Depends(get_db),
    _servico=Depends(require_service_key),
):
    if payload is None:
        payload = HeartbeatPayload()
    servico = db.query(ServicoMonitorado).filter(ServicoMonitorado.nome == nome).first()
    if not servico:
        raise HTTPException(status_code=404, detail=f"Serviço '{nome}' não encontrado.")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    servico.ultimo_heartbeat = now
    servico.status = payload.status
    servico.mensagem = payload.mensagem
    servico.atualizado_em = now
    db.commit()
