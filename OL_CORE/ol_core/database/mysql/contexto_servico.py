from ol_core.core.exceptions import ErroConexaoBanco
from datetime import datetime
from ol_core.core.logger import logger
from ol_core.core.conexao import executar


# ------------------------------------------------------------------
# SERVIÇOS
# ------------------------------------------------------------------
def atualizar_status_servico(nome: str, status: str, mensagem: str = None) -> None:
    """Status de monitoramento do serviço. Exceção à regra de propagar
    ErroConexaoBanco: é chamado também para REGISTRAR o erro de banco, e não
    pode derrubar o serviço por não conseguir se reportar."""
    try:
        executar(
            """
            UPDATE servico_monitorado SET ultimo_heartbeat = %s, status = %s, mensagem = %s WHERE nome = %s
            """,
            (datetime.now(), status, mensagem[:499] if mensagem else None, nome)
        )
    except ErroConexaoBanco as erro:
        logger.error(f"[atualizar_status_servico] status '{status}' de '{nome}' não gravado: {erro.detail}")
    except Exception as erro:
        logger.error(f"[atualizar_status_servico] {erro}")
