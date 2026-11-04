from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.logger import logger
from datetime import datetime
from ol_core.models.industria import Industria
from ol_core.models.pedido import Pedido
from ol_core.utils.disparar import envia_arquivo_para_pasta
from ol_core.database.sqlserver.contexto_produto import resgata_estoque
from ol_core.database.mysql.contexto_industria import buscar_fornecedores_industria
from ol_core.database.mysql.contexto_parametros import exigir_cnpj_distribuidor
from ol_core.layouts import formato_closeup as formato

def gerar_estoque_closeup(industria: Industria, pedido: Pedido):
    try:
        #==== NOME ARQUIVO ====
        PASTA_ESTOQUE = industria.pasta_estoque
        nome_arquivo_estoque = formato.NOME_ARQUIVO_ESTOQUE

        # Sem fornecedor cadastrado na indústria não há como saber quais
        # produtos são dela — e sem esse filtro iria o estoque do ERP inteiro.
        fornecedores = buscar_fornecedores_industria(industria.id_industria)
        if not fornecedores:
            logger.error(
                f"Estoque de {industria.nome} não gerado: nenhum código de fornecedor cadastrado "
                "na seção \"Fornecedores no ERP\" da indústria."
            )
            return

        #==== DADOS DISTRIBUIDOR =====
        # Antes, o CNPJ do distribuidor era fixo aqui no código.
        data_criacao = datetime.now()
        cnpj_distribuidor = exigir_cnpj_distribuidor()


        #==== DADOS PRODUTOS ====
        df_estoque = resgata_estoque(fornecedores)
        if df_estoque is None:
            logger.error(f"Estoque de {industria.nome} não gerado: a consulta de estoque não retornou produtos.")
            return

        df_estoque["chave"] = (
            df_estoque["Cod_barra"].astype(str).str.strip()
            + df_estoque["estoque_disponivel"].astype(str).str.strip()
        )
        df_estoque = df_estoque.sort_values(by="chave")

        registros = list(zip(
            df_estoque["Cod_barra"].astype(str).str.strip(),
            df_estoque["estoque_disponivel"].astype(str).str.strip(),
        ))


        #==== CRIANDO ARQUIVO ====
        caminho_completo = PASTA_ESTOQUE / nome_arquivo_estoque
        with open(caminho_completo, "w") as f:
            f.write(formato.primeira_linha_estoque(cnpj_distribuidor, data_criacao) + "\n")
            # Gerador: um registro inválido (nulo vindo do ERP) falha aqui, como sempre falhou.
            f.write("\n".join(formato.registro_estoque(cod, est) for cod, est in registros))


        #==== ENVIAR ARQUIVO ====
        envia_arquivo_para_pasta(caminho_completo, industria.pasta_estoque)
        logger.info("Arquivo de estoque enviado")
    except ErroConexaoBanco:
        raise
    except Exception as error:
        logger.error(f"ERRO AO GERAR ESTOQUE {industria.nome}\n {error}")
