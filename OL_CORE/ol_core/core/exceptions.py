class ErroValidacao(Exception):
    """Erro de validação de domínio (ex.: dados de pedido/cliente inválidos).

    Não depende de FastAPI para que o ol_core continue utilizável por
    processos batch (OL_Services) além da API (OL_API). Carrega
    `status_code`/`detail` para quem quiser converter em HTTPException
    na camada web.
    """

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class ErroConexaoBanco(Exception):
    """Falha de CONEXÃO com um banco (MySQL operacional ou SQL Server do ERP):
    servidor fora do ar, timeout de conexão/consulta, conexão perdida no meio
    da operação.

    Existe para separar "o banco caiu" de "a consulta não achou nada": as
    funções de contexto devolvem None/[]/False quando não há dados, e por isso
    NÃO podem engolir esta exceção — ela sempre propaga até a borda (API
    responde 503; serviços batch registram "Erro" e não movem arquivos).
    Erros de SQL comuns (sintaxe, constraint) não viram esta exceção.
    """

    MENSAGEM = "Houve um problema de conexão com o banco de dados"

    def __init__(self, banco: str, causa: str = "") -> None:
        self.banco = banco
        self.causa = causa
        self.detail = f"{self.MENSAGEM} ({banco}). Tente novamente em instantes."
        self.status_code = 503
        super().__init__(f"{self.detail} Causa: {causa}" if causa else self.detail)
