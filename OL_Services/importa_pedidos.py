import os

from ol_core.core.logger import logger # type: ignore
from ol_core.core.exceptions import ErroConexaoBanco # type: ignore
from ol_core.services.import_service import LayouFactory # type: ignore
from ol_core.layouts import Operacao, industria_suporta
from ol_core.core.variaveis_globais import industrias_ativas # type: ignore
from ol_core.core.config import inicializar_processo, pasta_da_aplicacao # type: ignore
from ol_core.utils.disparar import movimenta_arquivo_para_pasta # type: ignore
from ol_core.utils.manipula_arquivo import verifica_pedidos_recebidos # type: ignore
from ol_core.database.mysql.contexto_servico import atualizar_status_servico # type: ignore
from ol_core.database.mysql.contexto_arquivo import verifica_se_arquivo_existe # type: ignore

from ambiente_local import em_homologacao, garantir_ambiente_local, isolar_industria
from monta_arquivo_pedido import gerar_pedido_teste

_SERVICO = "importa_pedidos"

if __name__ == "__main__":
    inicializar_processo(_SERVICO, pasta_da_aplicacao(__file__))
    # Lido depois de carregar o .env (antes era lido no import, sem ele).
    _QTD_PEDIDOS_TESTE = int(os.getenv("HOMOLOG_QTD_PEDIDOS", "1"))

    if em_homologacao():
        garantir_ambiente_local()

    atualizar_status_servico(_SERVICO, "Executando")
    try:
        for industria in industrias_ativas():
            # Layout sem leitura de pedido: os arquivos ficam na pasta de envio
            # (antes cada um gerava um erro de importação a cada execução).
            if not industria_suporta(industria, Operacao.PEDIDO):
                continue

            if em_homologacao():
                # Homologação: pastas redirecionadas para OL_LOCAL e pedidos simulados no lugar do FTP.
                isolar_industria(industria)
                for _ in range(_QTD_PEDIDOS_TESTE):
                    gerar_pedido_teste(industria)

            logger.info(f"Verifcando lista de envio da {industria.nome}")

            lista_pedidos = verifica_pedidos_recebidos(str(industria.pasta_envio))
            if not lista_pedidos:
                logger.info(f"Nenhum arquivo encontrado para importação da OL {industria.nome}.")
                continue

            logger.info("Iniciando o processo de importação de pedidos no PAINEL OL")
            for arquivo in lista_pedidos:

                if not arquivo.suffix.lower() == ".txt":
                    logger.info(f"Arquivo {arquivo} não é um arquivo de texto. Pulando...\n\n")
                    continue

                logger.info(f"Importando arquivo: {arquivo}")

                if verifica_se_arquivo_existe(arquivo.name):
                    logger.info(f"Arquivo {arquivo} já foi importado. Pulando...\n\n")
                    continue

                # Só vai para o backup o que de fato foi gravado. Se a importação
                # falhou, nada ficou no banco (transação desfeita) e o arquivo
                # continua na pasta de envio para a próxima execução — movê-lo
                # aqui perdia o pedido. Queda do banco (ErroConexaoBanco)
                # interrompe o lote inteiro no except abaixo, sem mover nada.
                if LayouFactory.importar(industria, arquivo):
                    movimenta_arquivo_para_pasta(str(arquivo), str(industria.pasta_backup))
                else:
                    logger.error(
                        f"Importação de {arquivo.name} falhou; arquivo mantido em "
                        f"{industria.pasta_envio} para nova tentativa.\n\n"
                    )

        atualizar_status_servico(_SERVICO, "OK", "Importação concluída")
    except ErroConexaoBanco as e:
        logger.error(f"[{_SERVICO}] {e.detail} Lote interrompido; arquivos não importados continuam na pasta de envio. Causa: {e.causa}")
        atualizar_status_servico(_SERVICO, "Erro", e.detail)
    except Exception as e:
        logger.error(f"[{_SERVICO}] Erro: {e}")
        atualizar_status_servico(_SERVICO, "Erro", str(e))
