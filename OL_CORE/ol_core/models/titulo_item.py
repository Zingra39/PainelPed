class Titulo_Item:
    def __init__(
            self,
            codigo_produto: int,
            ean: str,
            quantidade_atendida: int,
            desconto: float,
            prazo: int,
            quantidade_solicitada: int,
            produtos_motivo: int,
            preco: float
        ):
        self.codigo_produto = codigo_produto
        self.ean = ean
        self.quantidade_atendida = quantidade_atendida
        self.desconto = desconto
        self.prazo = prazo
        self.produtos_motivo = produtos_motivo
        self.quantidade_solicitada = quantidade_solicitada
        self.preco = preco
