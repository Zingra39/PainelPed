class Pedido_Item:
    def __init__(
            self,
            numero_pedido_ol: str = "",
            cnpj_cliente: str = "",
            codigo_produto: int = 0,
            ean: str = "",
            quantidade_atendida: int = 0,
            quantidade_solicitada: int = 0,
            preco: float = 0.00,
            desconto: float = 0.00,
            condicao: str = "",
            id_cond: int = 0,
            cod_motivo: int = 0
        ):
        self.numero_pedido_ol = numero_pedido_ol
        self.cnpj_cliente = cnpj_cliente
        self.codigo_produto = codigo_produto
        self.ean = ean
        self.quantidade_atendida = quantidade_atendida
        self.quantidade_solicitada = quantidade_solicitada
        self.preco = preco
        self.desconto = desconto
        self.id_cond = id_cond
        self.condicao = condicao
        self.cod_motivo = cod_motivo
