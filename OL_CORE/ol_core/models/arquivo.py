from datetime import datetime


class Arquivo:
    def __init__(
        self,
        numero_pedido_ol: str,
        nome: str,
        tipo: str,
        hash: str,
        caminho: str,
        situacao: str,
        criado_em: datetime
    ):
        self.numero_pedido_ol = numero_pedido_ol
        self.nome = nome
        self.tipo = tipo or None
        self.hash = hash or None
        self.caminho = caminho
        self.situacao = situacao or None
        self.criado_em = criado_em
