from datetime import datetime

from ol_core.database.mysql.contexto_arquivo import verifica_se_arquivo_existe
from ol_core.core.logger import logger 
from ol_core.utils.substituir import corrige_cond_vitamina 
from ol_core.utils.disparar import envia_arquivo_para_pasta 
from ol_core.core.variaveis_globais import industrias_ativas
from ol_core.core.config import inicializar_processo, pasta_da_aplicacao
from ol_core.models.enums.tipo_status_oper import TipoStatusOper 
from ol_core.database.mysql.contexto_industria import buscar_industria_ftp 
from ol_core.database.mysql.contexto_servico import atualizar_status_servico 
from ol_core.services.conectar_ftp import deletar_arquivo_ftp, retorna_arquivos_ftp, baixar_arquivo_ftp 
from ol_core.database.mysql.contexto_arquivo import registrar_arquivo_baixado_ftp, verifica_se_arquivo_baixado_existe, atualizar_situacao_arquivo_pelo_nome, atualizar_situacao_arquivo_baixado_ftp

_SERVICO = "coleta_pedidos_ftp"

def verificar_data_pedido(arquivo: str) -> bool:
    ano = str(arquivo)[7:11]
    mes = str(arquivo)[11:13]
    dia = str(arquivo)[13:15]
    data_formatada = f"{dia}-{mes}-{ano}"

    # Converte data_formatada para datetime
    pedido_data = datetime.strptime(data_formatada, "%d-%m-%Y")
    
    # Aceita apenas pedidos a partir de 01/10/2026
    return pedido_data >= datetime(2026, 10, 1)

if __name__ == "__main__":
    inicializar_processo(_SERVICO, pasta_da_aplicacao(__file__))
    try:
        industria = next((i for i in industrias_ativas() if i.nome == "Hypera"), None)
        if not industria:
            raise RuntimeError("Indústria Hypera não encontrada na base de dados.")

        ftp_config = buscar_industria_ftp(industria.id_industria)
        if not ftp_config:
            raise RuntimeError(f"Configuração FTP não encontrada para a indústria {industria.nome}.")

        logger.info("Iniciando o processo de coleta de pedidos")
        atualizar_status_servico(_SERVICO, "Executando")

        arquivos_ftp = retorna_arquivos_ftp(ftp_config["ftp_pedidos"])

        logger.info(f"Arquivos encontrados no FTP: {len(arquivos_ftp)}")

        if arquivos_ftp:
            for arquivo in arquivos_ftp:
                logger.info(f"Baixando arquivo: {arquivo}") 
                
                # if not verificar_data_pedido(str(arquivo)):
                #     logger.info("Pedido antigo, pulando....\n")
                #     deletar_arquivo_ftp(ftp_config["ftp_pedidos"], arquivo)
                #     continue

                if verifica_se_arquivo_baixado_existe(arquivo) and verifica_se_arquivo_existe(arquivo):
                    logger.info(f"Arquivo {arquivo} já foi processado. Pulando...\n")
                    deletar_arquivo_ftp(ftp_config["ftp_pedidos"], arquivo)
                    continue
                
                if not verifica_se_arquivo_baixado_existe(arquivo):
                    registrar_arquivo_baixado_ftp(arquivo, "Baixando")


                caminho_local = baixar_arquivo_ftp(
                    ftp_config["ftp_pedidos"],
                    arquivo,
                    str(industria.pasta_envio)
                )

                if not caminho_local:
                    logger.error(f"Falha ao baixar o arquivo {arquivo}. Pulando para o próximo.\n")
                    continue
                else:
                    atualizar_situacao_arquivo_baixado_ftp(arquivo, "Baixado")
                    
                if industria.pasta_pedido_original is None:
                    logger.error("Pasta de pedido original não configurada para a indústria Hypera.")
                    continue

                arquivoEnviado = envia_arquivo_para_pasta(caminho_local, industria.pasta_pedido_original)

                if corrige_cond_vitamina(caminho_local, arquivo, str(industria.pasta_envio)):
                    atualizar_situacao_arquivo_pelo_nome(arquivo, "Baixado com Vitamina")
                
                if arquivoEnviado:
                    logger.info(f"Arquivo {arquivo} enviado para a pasta de pedidos originais.")
                    deletar_arquivo_ftp(ftp_config["ftp_pedidos"], arquivo)
        else:
            logger.warning("Nenhum arquivo encontrado no FTP.")

        atualizar_status_servico(_SERVICO, "OK", "Coleta via FTP concluída")
    except Exception as e:
        logger.error(f"[{_SERVICO}] Erro: {e}")
        atualizar_status_servico(_SERVICO, "Erro", str(e))
