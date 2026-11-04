import ftplib
import os
from ol_core.core.config import ambiente, credenciais_ftp, em_producao
from ol_core.core.logger import logger


def _conectar(caminho_ftp: str) -> ftplib.FTP:
    """Abre a sessão FTP já no diretório informado. Credenciais lidas na hora
    (nunca congeladas no import), então valem as do processo em execução."""
    servidor, usuario, senha = credenciais_ftp()
    if not servidor or not usuario or not senha:
        raise ValueError("FTP_SERVER, FTP_USER e FTP_PASSWORD devem estar configurados no ambiente")
    ftp = ftplib.FTP(servidor, timeout=30)
    ftp.login(usuario, senha)
    ftp.cwd(caminho_ftp)
    return ftp


def retorna_arquivos_ftp(caminho_ftp: str) -> list:
    """Retorna todos os arquivos do caminho FTP informado."""
    try:
        ftp = _conectar(caminho_ftp)

        arquivos = [nome for nome, facts in ftp.mlsd() if facts.get("type") == "file"]

        ftp.quit()
        return arquivos

    except Exception as e:
        logger.error(f"Erro ao conectar ao FTP: {e}")
        return []


def envia_arquivo_ftp(caminho_ftp: str, arquivo: str) -> None:
    """Envia um arquivo para o caminho FTP informado."""
    
    if not em_producao():
        logger.warning(f"Ambiente {ambiente()} não suporta envio de arquivos ao FTP. Ignorando.")
        return
    
    try:
        ftp = _conectar(caminho_ftp)

        with open(arquivo, 'rb') as f:
            ftp.storbinary(f'STOR {os.path.basename(arquivo)}', f)

        ftp.quit()
        logger.info(f"Arquivo enviado ao FTP: {os.path.basename(arquivo)}")

    except Exception as e:
        logger.error(f"Erro ao enviar arquivo ao FTP: {e}")


def deletar_arquivo_ftp(caminho_ftp: str, nome_arquivo: str) -> None:
    """Remove um arquivo do caminho FTP informado."""
    try:
        ftp = _conectar(caminho_ftp)
        ftp.delete(nome_arquivo)
        ftp.quit()
        logger.info(f"Arquivo removido do FTP: {nome_arquivo}")

    except Exception as e:
        logger.error(f"Erro ao deletar arquivo {nome_arquivo}: {e}")


def baixar_arquivo_ftp(caminho_ftp: str, nome_arquivo: str, pasta_destino: str) -> str | None:
    """
        Baixa um arquivo específico do caminho FTP e salva na pasta destino.

        Returns:
            Caminho completo do arquivo baixado, ou None em caso de erro.
    """
    try:
        ftp = _conectar(caminho_ftp)

        caminho_local = os.path.join(pasta_destino, nome_arquivo)
        with open(caminho_local, "wb") as f:
            ftp.retrbinary(f"RETR {nome_arquivo}", f.write)

        ftp.quit()
        return caminho_local

    except Exception as e:
        logger.error(f"Erro ao baixar arquivo {nome_arquivo}: {e}")
        return None
