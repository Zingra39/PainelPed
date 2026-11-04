from enum import Enum


class TipoSeveridade(Enum):
    INFO = "INFO"
    ALERTA = "ALERTA"
    ERRO = "ERRO"
    CRITICO = "CRITICO"
    FATAL = "FATAL"
    IGNORADO = "IGNORADO"
