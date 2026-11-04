class Titulo:
    def __init__(
            self,
            codigo_pedido_interno: int,
            nome_arquivo: str,
            cnpj_cliente: str,
            numero_pedido_ol: str,
            data_emissao: str,
            data_vencimento: str,
            codigo_titulo: int,
            numero_titulo: str,
            serie_nf: int,
            codigo_situacao: int,
            data_cancelamento: str,
            quem_cancelou: str,
            chave_acesso: str,
        ):
        self.codigo_pedido_interno = codigo_pedido_interno
        self.nome_arquivo = nome_arquivo
        self.cnpj_cliente = cnpj_cliente
        self.numero_pedido_ol = numero_pedido_ol
        self.data_emissao = data_emissao
        self.data_vencimento = data_vencimento
        self.numero_titulo = numero_titulo
        self.codigo_titulo = codigo_titulo
        self.codigo_situacao = codigo_situacao
        self.data_cancelamento = data_cancelamento
        self.quem_cancelou = quem_cancelou
        self.serie_nf = serie_nf
        self.chave_acesso = chave_acesso
