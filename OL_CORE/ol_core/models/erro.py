from datetime import datetime

# Valores gravados em pedido_ocorrencia.resolvido (VARCHAR(100)).
RESOLVIDO_ABERTO = "0"
RESOLVIDO_SIM = "1"
RESOLVIDO_IGNORADO = "ignorado"


class Erro:
    def __init__(
        self,
        numero_pedido_ol: str,
        severidade: str = "",
        descricao: str = "",
        resolvido: int | str = 0,
        criado_em: datetime = datetime.now()
    ):
        self.numero_pedido_ol = numero_pedido_ol or None
        self.severidade = severidade or None
        self.descricao = descricao
        self.resolvido = resolvido
        self.criado_em = criado_em
