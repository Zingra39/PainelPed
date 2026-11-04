
import os
import time
import shutil
from ol_core.core.logger import logger


def corrige_cond_vitamina(caminho_arquivo: str, arquivo: str, diretorio_destino: str) -> bool:
    """
        Processa um único arquivo: valida, move e substitui código
    """
    try:
        # Aguarda um pouco para garantir que o arquivo foi completamente escrito
        time.sleep(0.5)

        # Verifica se o arquivo ainda existe (pode ter sido movido por outro processo)
        if not os.path.exists(caminho_arquivo):
            logger.warning(f"Arquivo {arquivo} nao existe mais no origem")
            return False

        # Lê o arquivo
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            linhas = f.readlines()

        # Verifica se precisa processar
        arquivo_valido = False

        codigos_substituicao = {
            "8067": "8107",
            "9143": "8107",
            "9144": "8107",
            "9145": "8107",
            "9146": "8107"
        }

        # Percorre as linhas para validar o arquivo (condição: linha começa com '2' e tem '8067' na posição 94-97)
        for linha in linhas:
            linha_limpa = linha.rstrip("\n")
            if linha_limpa.lstrip().startswith('2') and len(linha_limpa) >= 97:
                codigo = linha_limpa[93:97]

                if codigo in codigos_substituicao:
                    arquivo_valido = True
                    break

        if not arquivo_valido:
            logger.info(f"Arquivo {arquivo} não atende aos criterios de vitaminas - ignorado \n")
            return False

        # Substitui o código nas linhas
        linhas_modificadas = []

        for linha in linhas:
            nova_linha = linha

            for codigo_origem, codigo_destino in codigos_substituicao.items():
                nova_linha = nova_linha.replace(codigo_origem, codigo_destino)

            linhas_modificadas.append(nova_linha)

        # Move o arquivo para destino
        novo_caminho = os.path.join(diretorio_destino, arquivo)
        shutil.move(caminho_arquivo, novo_caminho)

        # Salva as modificações
        with open(novo_caminho, 'w', encoding='utf-8') as f:
            f.writelines(linhas_modificadas)

        logger.info(f"✓ Processado com sucesso: {arquivo}\n")
        return True

    except PermissionError:
        logger.warning(f"Arquivo {arquivo} esta em uso - tentando novamente em 2s")
        time.sleep(2)

        # Tenta novamente uma vez
        try:
            return corrige_cond_vitamina(caminho_arquivo, arquivo, diretorio_destino)
        except:
            logger.error(f"Nao foi possivel processar {arquivo} - arquivo em uso\n")
            return False

    except Exception as e:
        logger.error(f"Erro ao processar {arquivo}: {e}\n")
        return False
