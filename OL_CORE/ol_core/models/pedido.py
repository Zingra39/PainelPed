from ol_core.models.pedido_item import Pedido_Item

class Pedido:
    def __init__(
            self,
            id_industria: int = 0,
            nome_arquivo: str = "",
            cnpj_cliente: str = "",
            situacao_cliente: int = 0,
            codigo_interno_pedido: int = 0,
            condicao: str = "",
            numero_pedido_ol: str = "",
            data_pedido: str = "",
            observacao: str = "",
            cod_situacao: int = 0,
            situacao: str = "",
            data_cancelamento: str = "",
            quem_cancelou: str = "",
            data_faturamento: str = "",
            valor_total: float = 0,
            id_cond: int = 0,
            itens: list[Pedido_Item] = []
        ):
        self.id_industria = id_industria or 0
        self.nome_arquivo = nome_arquivo or None
        self.cnpj_cliente = cnpj_cliente or None
        self.situacao_cliente = situacao_cliente or None
        self.codigo_interno_pedido = codigo_interno_pedido or 0
        self.condicao = condicao or None
        self.numero_pedido_ol = numero_pedido_ol or None
        self.data_pedido = data_pedido or None
        self.observacao = observacao or ""
        self.cod_situacao = cod_situacao
        self.situacao = situacao
        self.data_cancelamento = data_cancelamento or None
        self.quem_cancelou = quem_cancelou or None
        self.data_faturamento = data_faturamento or None
        self.valor_total = valor_total
        self.id_cond = id_cond or 0
        self.itens = itens or []
