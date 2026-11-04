from datetime import date
from typing import Optional

from pydantic import BaseModel


class DashboardCards(BaseModel):
    total_recebidos: int
    total_importados: int
    total_pendentes: int
    total_prontos_transmissao: int
    total_retornos_gerados: int
    total_espelhos_gerados: int
    total_cancelamentos_gerados: int


class MotivoCancelamentoItem(BaseModel):
    motivo: str
    total: int


class ArquivosPorDiaItem(BaseModel):
    data: date
    retorno: int
    espelho: int
    cancelamento: int


class PedidosFaturadosPorDiaItem(BaseModel):
    data: date
    total: int


class TopProdutoItem(BaseModel):
    ean: str
    descricao: Optional[str] = None
    quantidade_solicitada: int
