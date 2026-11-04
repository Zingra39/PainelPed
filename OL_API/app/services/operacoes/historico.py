"""Registro das ações manuais no histórico do pedido."""
from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.logger import logger
from ol_core.database.mysql.contexto_historico import registrar_historico


def _log(numero_pedido_ol: str, acao: str, detalhe: str, id_usuario: int):
    try:
        registrar_historico(numero_pedido_ol, acao, detalhe, id_usuario)
    except ErroConexaoBanco:
        raise
    except Exception as e:
        logger.error(f"Erro ao registrar histórico de ação: {e}")
        pass


def registrar_log_observacao(numero_pedido_ol: str, observacao: str, id_usuario: int) -> None:
    """Histórico da edição de observação feita na triagem."""
    detalhe = f"Observação definida como: '{observacao}'." if observacao else "Observação removida."
    _log(numero_pedido_ol, "Observação alterada", detalhe, id_usuario)


def registrar_log_analise(numero_pedido_ol: str, acao: str, detalhe: str, id_usuario: int) -> None:
    """Histórico do início/encerramento da análise ("Em Analise") do pedido."""
    _log(numero_pedido_ol, acao, detalhe, id_usuario)
