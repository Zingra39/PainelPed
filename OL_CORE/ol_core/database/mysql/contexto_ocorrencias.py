from ol_core.core.exceptions import ErroConexaoBanco
from datetime import datetime, timedelta
from ol_core.core.logger import logger
from ol_core.core.conexao import buscar_todos, executar, inserir
from ol_core.models.erro import Erro, RESOLVIDO_ABERTO, RESOLVIDO_SIM, RESOLVIDO_IGNORADO


# ------------------------------------------------------------------
# OCORRÊNCIAS
# ------------------------------------------------------------------
def buscar_ocorrencias_nao_resolvidas(numero_pedido_ol: str) -> list[dict]:
    try:
        df = buscar_todos(
            """
            SELECT id, severidade, codigo, descricao, criado_em
            FROM pedido_ocorrencia
            WHERE numero_pedido_ol = %s AND resolvido = '0'
            ORDER BY criado_em DESC
            """,
            (numero_pedido_ol,)
        )
        
        if not df or len(df) == 0:
            return []
            
        return df
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[buscar_ocorrencias_nao_resolvidas] {erro}")
        return []

def _status_resolvido(valor) -> str:
    if isinstance(valor, str) and valor.strip().lower() == RESOLVIDO_IGNORADO:
        return RESOLVIDO_IGNORADO
    return RESOLVIDO_SIM if valor and str(valor) != RESOLVIDO_ABERTO else RESOLVIDO_ABERTO


def registrar_ocorrencia(erro: Erro) -> None:
    # `resolvido` vem do próprio Erro: os validadores marcam "ignorado" (com
    # severidade IGNORADO) quando o parâmetro de ignorar a ocorrência está
    # ligado. Gravar "0" fixo aqui fazia a ocorrência ignorada seguir "não
    # resolvida" e manter o pedido em "Verificar" (ver buscar_ocorrencias_nao_resolvidas).
    try:
        inserir(
            """
            INSERT INTO pedido_ocorrencia
                (numero_pedido_ol, severidade, codigo, descricao, resolvido, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (erro.numero_pedido_ol, erro.severidade, "0", erro.descricao, _status_resolvido(erro.resolvido), datetime.now())
        )
    except ErroConexaoBanco:
        raise
    except Exception as err:
        logger.error(f"[registrar_ocorrencia] {err}")


def registrar_ocorrencia_item(id_pedido_item: int, descricao: str) -> None:
    try:
        inserir(
            """
            INSERT INTO pedido_item_ocorrencia
                (id_pedido_item, severidade, codigo, descricao, criado_em)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (id_pedido_item, "0", "0", descricao, datetime.now())
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[registrar_ocorrencia_item] {erro}")


def marcar_ocorrencias_resolvidas(numero_pedido_ol: str) -> None:
    try:
        executar(
            "UPDATE pedido_ocorrencia SET resolvido = '1' WHERE numero_pedido_ol = %s AND resolvido = '0'",
            (numero_pedido_ol,)
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[marcar_ocorrencias_resolvidas] {erro}")


def marcar_ocorrencias_item_resolvidas(numero_pedido_ol: str) -> None:
    try:
        executar(
            """
            UPDATE pedido_item_ocorrencia pio
            JOIN pedido_item pi ON pi.id = pio.id_pedido_item
            SET pio.resolvido = 1
            WHERE pi.numero_pedido_ol = %s AND pio.resolvido = 0
            """,
            (numero_pedido_ol,)
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[marcar_ocorrencias_item_resolvidas] {erro}")


def limpar_ocorrencias_resolvidas_antigas(dias: int = 30) -> None:
    try:
        limite = datetime.now() - timedelta(days=dias)
        executar(
            "DELETE FROM pedido_ocorrencia WHERE resolvido <> '0' AND criado_em < %s",
            (limite,)
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[limpar_ocorrencias_resolvidas_antigas] {erro}")
