from enum import Enum


class TipoArquivo(Enum):
    RETORNO = "retorno"
    PEDIDO = "pedido"
    ESPELHO = "espelho"
    CANCELADO = "cancelado"
