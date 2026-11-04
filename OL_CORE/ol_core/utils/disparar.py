import os
import shutil
from pathlib import Path
from ol_core.core.logger import logger


def envia_arquivo_para_pasta(arquivo: str, pasta: Path) -> bool:
    """
        Move um arquivo para uma pasta específica. Se a pasta não existir, ela será criada.
    """
    try:
        # Cria a pasta se não existir
        pasta.mkdir(parents=True, exist_ok=True)

        # Move o arquivo para a pasta
        shutil.move(arquivo, pasta / Path(arquivo).name)
        logger.info(f"Arquivo {arquivo} movido para {pasta}")
        return True
    except Exception as e:
        logger.error(f"Erro ao mover o arquivo {arquivo} para {pasta}: {e}")
        return False
    
def movimenta_arquivo_para_pasta(arquivo: str, pasta: str):
    if os.path.exists(os.path.join(pasta, os.path.basename(arquivo))):
        logger.warning(f"Arquivo {arquivo} já existe na pasta {pasta}.")
        return
    
    
    shutil.move(arquivo, pasta)
    logger.info(f"Arquivo movimentado para pasta: {pasta}")
