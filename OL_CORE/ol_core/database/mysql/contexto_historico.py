from ol_core.core.exceptions import ErroConexaoBanco
from datetime import datetime
from ol_core.core.logger import logger
from ol_core.core.conexao import inserir, buscar_um


# ------------------------------------------------------------------
# HISTÓRICO
# ------------------------------------------------------------------
def registrar_historico(numero_pedido_ol: str, acao: str, detalhe: str = None, id_usuario: int = None) -> None:
    try:
        inserir(
            """
            INSERT INTO pedido_historico
                (numero_pedido_ol, id_usuario, acao, detalhe, criado_em)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (numero_pedido_ol, id_usuario, acao, detalhe, datetime.now())
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[registrar_historico] {erro}")


# ------------------------------------------------------------------
# USUÁRIO "SISTEMA"
# ------------------------------------------------------------------
_EMAIL_USUARIO_SISTEMA = "sistema@painelol.local"
_id_usuario_sistema_cache: int | None = None


def obter_id_usuario_sistema() -> int | None:
    """Id do usuário "Sistema" (ativo=0, sem login), usado como id_usuario em
    pedido_historico quando a ação é automática — ex: transmissão automática
    via parâmetro `transmissao_automatica_pronto`.

    O resultado é cacheado em memória: esse id não muda em runtime, então
    não há motivo pra consultar o banco de novo a cada chamada. Devolve None
    (sem lançar exceção) se o usuário não existir ou em caso de erro — quem
    chama deve tratar isso registrando o histórico com id_usuario=None em
    vez de falhar a operação por causa disso.
    """
    global _id_usuario_sistema_cache
    if _id_usuario_sistema_cache is not None:
        return _id_usuario_sistema_cache
    try:
        resultado = buscar_um("SELECT id FROM usuario WHERE email = %s", (_EMAIL_USUARIO_SISTEMA,))
        if resultado:
            _id_usuario_sistema_cache = resultado["id"]
        return resultado["id"] if resultado else None
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[obter_id_usuario_sistema] {erro}")
        return None
