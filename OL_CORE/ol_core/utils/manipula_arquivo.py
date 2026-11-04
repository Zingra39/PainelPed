from pathlib import Path

from ol_core.core.logger import logger


def verifica_pedidos_recebidos(PASTA_ENVIO: str) -> list:
    lista_pedidos = []

    for arquivo in Path(PASTA_ENVIO).glob("*.txt"):
        if arquivo.is_file():
            lista_pedidos.append(arquivo)
        else:
            logger.warning(f"Arquivo não encontrado: {arquivo.name}")

    if not lista_pedidos:
        logger.warning(f"Nenhum arquivo encontrado na pasta de envio.")
        return []

    logger.info(f"Total de arquivos encontrados: {len(lista_pedidos)}")
    return lista_pedidos
