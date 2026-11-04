from ol_core.core.exceptions import ErroConexaoBanco
from datetime import datetime
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from ol_core.core.logger import logger
from ol_core.core.conexao import buscar_um, executar, inserir
from ol_core.models.arquivo import Arquivo


# ------------------------------------------------------------------
# ARQUIVO
# ------------------------------------------------------------------
def registrar_arquivo(arquivo: Arquivo, situacao: str) -> int | None:
    try:
        return inserir(
            """
            INSERT INTO arquivo
                (numero_pedido_ol, nome, tipo, hash_md5, caminho, situacao, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (arquivo.numero_pedido_ol, arquivo.nome, arquivo.tipo, arquivo.hash, arquivo.caminho, situacao, datetime.now())
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[registrar_arquivo] {erro}")
        return None


def atualizar_situacao_arquivo(id_arquivo: int, situacao: str) -> None:
    try:
        executar(
            "UPDATE arquivo SET situacao = %s WHERE id = %s",
            (situacao, id_arquivo)
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[atualizar_situacao_arquivo] {erro}")


def atualizar_situacao_arquivo_pelo_nome(nome: str, situacao: str) -> None:
    try:
        executar(
            "UPDATE arquivo_baixado_ftp SET situacao = %s WHERE nome = %s",
            (situacao, nome)
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[atualizar_situacao_arquivo] {erro}")


def verifica_se_arquivo_existe(nome_arquivo: str) -> bool:
    try:
        resultado =  buscar_um("SELECT id FROM arquivo WHERE nome = %s", (nome_arquivo,))
        return resultado["id"] if resultado else False
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verifica_se_arquivo_existe] {erro}")
        return False


def verificar_cancelado_existente(numero_pedido_ol: str) -> int | None:
    try:
        resultado = buscar_um(
            "SELECT id FROM arquivo WHERE numero_pedido_ol = %s AND tipo = 'cancelado' AND situacao = %s",
            (numero_pedido_ol, TipoStatusOper.CANCELADO.value)
        )
        return resultado["id"] if resultado else None
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verificar_retorno_existente] {erro}")
        return None


def verificar_tipo_de_arquivo_existente(numero_pedido_ol: str, tipo_arquivo: str) -> bool:
    try:
        resultado = buscar_um(
            "SELECT id FROM arquivo WHERE numero_pedido_ol = %s AND tipo = %s AND situacao = %s",
            (numero_pedido_ol, tipo_arquivo, TipoStatusOper.RETORNO.value)
        )

        if resultado is None:
            return False

        return resultado.get("id") is not None
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verificar_retorno_existente] {erro}")
        return False


def verificar_retorno_existente(numero_pedido_ol: str) -> int | None:
    """Devolve o id do arquivo de retorno já registrado para o pedido, se existir.

    Mesma assinatura de verificar_espelho_existente/verificar_cancelado_existente —
    antes devolvia bool, o que forçava retorno_service.gerar_retorno_closeup a usar
    resgata_arquivo_id (sem filtro de tipo) pra conseguir o id, atualizando por engano
    a situacao do arquivo ERRADO (o "pedido" importado, não um "retorno")."""
    try:
        resultado = buscar_um(
            "SELECT id FROM arquivo WHERE numero_pedido_ol = %s AND tipo = 'retorno'",
            (numero_pedido_ol,)
        )
        return resultado["id"] if resultado else None
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verificar_retorno_existente] {erro}")
        return None


def verificar_espelho_existente(numero_pedido_ol: str) -> int | None:
    try:
        resultado = buscar_um(
            "SELECT id FROM arquivo WHERE numero_pedido_ol = %s AND tipo = 'espelho'",
            (numero_pedido_ol,)
        )
        return resultado["id"] if resultado else None
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verificar_espelho_existente] {erro}")
        return None


def registrar_arquivo_baixado_ftp(arquivo: str, situacao: str) -> int | None:
    try:
        return inserir(
            "INSERT INTO arquivo_baixado_ftp (nome, situacao, baixado_em) VALUES (%s, %s, %s)",
            (arquivo, situacao, datetime.now())
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[registrar_arquivo_baixado_ftp] {erro}")
        return None


def verifica_se_arquivo_baixado_existe(nome_arquivo: str) -> bool:
    try:
        df = buscar_um("SELECT id FROM arquivo_baixado_ftp WHERE nome = %s", (nome_arquivo,))
        return df is not None
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verifica_se_arquivo_baixado_existe] {erro}")
        return False


def atualizar_situacao_arquivo_baixado_ftp(nome: str, situacao: str) -> None:
    try:
        executar(
            "UPDATE arquivo_baixado_ftp SET situacao = %s WHERE nome = %s",
            (situacao, nome)
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[atualizar_situacao_arquivo_baixado] {erro}")


def resgata_arquivo_id(numero_pedido_ol: str) -> int | None:
    try:
        resultado = buscar_um(
            "SELECT id FROM arquivo WHERE numero_pedido_ol = %s",
            (numero_pedido_ol,)
        )
        return resultado["id"] if resultado else None
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[resgata_arquivo_id] {erro}")
        return None