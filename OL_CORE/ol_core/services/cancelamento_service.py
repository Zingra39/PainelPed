from ol_core.core.exceptions import ErroConexaoBanco
import os
from datetime import datetime
from ol_core.database.sqlserver.contexto_cancelamento import verifica_motivo_cancelamento
from ol_core.database.mysql.contexto_parametros import exigir_cnpj_distribuidor
from ol_core.core.logger import logger
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.pedido import Pedido
from ol_core.models.arquivo import Arquivo
from ol_core.models.industria import Industria
from ol_core.services.conectar_ftp import envia_arquivo_ftp
from ol_core.utils.tratamento import trata_textos
from ol_core.layouts import formato_closeup as formato
from ol_core.models.enums.tipo_arquivo import TipoArquivo
from ol_core.utils.disparar import envia_arquivo_para_pasta
from ol_core.validators.validador import valida_ean, valida_motivo
from ol_core.database.mysql.contexto_pedidos import atualizar_motivo_cancelamento_pedido, atualizar_status_pedido, atualizar_status_erp_pedido
from ol_core.database.mysql.contexto_pedidos import verificar_itens_pedido_pelo_nome_arquivo_mysql
from ol_core.database.sqlserver.contexto_pedido import verifica_itens_pedido_pelo_cod_pedido
from ol_core.database.mysql.contexto_arquivo import atualizar_situacao_arquivo, registrar_arquivo, verificar_cancelado_existente
from ol_core.services.merge_itens_pedido import combinar_itens_sql_e_mysql


def verificar_itens_pedido_cancelamento(pedido: Pedido) -> list:
    """Busca os itens do pedido combinando Delage (SQL Server) e MySQL (painel).

    Mesma lógica de retorno_service.verificar_itens_pedido: quando o Delage
    não tem NENHUM item pro pedido (produto não cadastrado lá), cai
    integralmente pros dados do MySQL, em vez de descartar um pedido cujos
    dados originais (ean, quantidade etc.) o painel já tem.
    """
    itens_sql = verifica_itens_pedido_pelo_cod_pedido(pedido.codigo_interno_pedido)
    itens_mysql = (
        verificar_itens_pedido_pelo_nome_arquivo_mysql(pedido.nome_arquivo)
        if pedido.nome_arquivo
        else None
    )

    if not itens_sql and itens_mysql:
        logger.warning(
            f"Pedido {pedido.numero_pedido_ol} sem itens no Delage — "
            "usando os itens do MySQL (painel) como origem."
        )

    return combinar_itens_sql_e_mysql(itens_sql, itens_mysql)

def gerar_cancelado_closeup(industria: Industria, pedido: Pedido) -> bool:
    id_arquivo = None
    numero_pedido_ol = None
    try:
        #=== NOME ARQUIVO ====

        PASTA_OUTPUT = industria.pasta_cancelamento

        numero_pedido_ol = pedido.numero_pedido_ol

        if numero_pedido_ol is None:
            raise ValueError("Número de pedido não informado")

        if not PASTA_OUTPUT:
            logger.warning("Pasta de cancelamento não configurada")
            return False

        if not os.path.exists(PASTA_OUTPUT):
            os.makedirs(PASTA_OUTPUT)


        if pedido.cnpj_cliente:
            cnpj_cliente = trata_textos(pedido.cnpj_cliente, 'r', 14,"0")
            if "<Error>" in cnpj_cliente:
                return False
        else:
            # Sem CNPJ no pedido, sai do nome do arquivo (ou zeros, se não houver).
            nome_arquivo = os.path.basename(pedido.nome_arquivo or "")
            cnpj_cliente = formato.cnpj_do_nome_arquivo(nome_arquivo) or "".rjust(14, "0")

        nome_arquivo = formato.nome_arquivo_cancelamento(numero_pedido_ol, cnpj_cliente)

        arquivo_cancelamento = Arquivo(
            nome=nome_arquivo,
            numero_pedido_ol=numero_pedido_ol,
            caminho = os.path.join(PASTA_OUTPUT, nome_arquivo),
            criado_em=datetime.now(),
            tipo=TipoArquivo.CANCELADO.value,
            hash="",
            situacao=TipoStatusOper.GERANDO_CANCELAMENTO.value
        )


        #==== VALIDA ARQUIVO ====
        id_arquivo = verificar_cancelado_existente(numero_pedido_ol)

        if id_arquivo is None:
            id_arquivo = registrar_arquivo(arquivo_cancelamento, TipoStatusOper.GERANDO_CANCELAMENTO.value)
        else:
            atualizar_situacao_arquivo(id_arquivo, TipoStatusOper.GERANDO_CANCELAMENTO.value)

        #==== DADOS DISTRIBUIDOR ====
        # Lido aqui (e não no início): se faltar, a exceção cai no except com o
        # pedido e o arquivo já identificados, que são marcados como falha.
        cnpj_distribuidor = exigir_cnpj_distribuidor()

        #==== DADOS ITENS ====
        pedido_itens = verificar_itens_pedido_cancelamento(pedido)
        if not pedido_itens:
            logger.warning(f"Pedido {numero_pedido_ol} não possui itens para cancelamento.")
            if id_arquivo:
                atualizar_situacao_arquivo(id_arquivo, TipoStatusOper.FALHA_CANCELAMENTO.value)
            atualizar_status_pedido(numero_pedido_ol, TipoStatusOper.FALHA_CANCELAMENTO.value)
            return False

        # (EAN validado, quantidade solicitada, motivo) — validações na mesma ordem de sempre.
        itens = []
        for item in pedido_itens:
            ean = valida_ean(numero_pedido_ol, item.codigo_produto, item.ean)
            qtd_solicitada = int(item.quantidade_solicitada)
            cod_motivo = valida_motivo(item, pedido, cnpj_cliente)
            itens.append((ean, qtd_solicitada, cod_motivo))


        #==== DADOS DATA CANCELAMENTO ====
        if isinstance(pedido.data_cancelamento, str):
            data_cancelamento = pedido.data_cancelamento
        elif pedido.data_cancelamento is not None:
            data_cancelamento = formato.data_cancelamento_do_arquivo(pedido.data_cancelamento)
        else:
            data_cancelamento = formato.data_cancelamento_do_arquivo(datetime.now())


        # ==== CRIA ARQUIVO ====
        caminho_completo = os.path.join(PASTA_OUTPUT, nome_arquivo)

        with open(caminho_completo, "w") as arquivo:
            arquivo.write(formato.conteudo_cancelamento(
                cnpj_distribuidor, cnpj_cliente, numero_pedido_ol, itens, data_cancelamento,
            ))

        motivo = verifica_motivo_cancelamento(pedido.codigo_interno_pedido)
        if motivo is None: motivo = "Arquivo Cancelado"

        if id_arquivo:
            atualizar_situacao_arquivo(id_arquivo, TipoStatusOper.CANCELADO.value)
            atualizar_status_pedido(numero_pedido_ol, TipoStatusOper.CANCELADO.value)
            atualizar_motivo_cancelamento_pedido(numero_pedido_ol, motivo)

        envia_arquivo_ftp('/46239901000131/CANCELAMENTO',caminho_completo)
        logger.info(f"Cancelamento enviado via FTP: {nome_arquivo}")


        # ==== ENVIA ARQUIVO ====
        if not industria.pasta_envio_cancelamento:
            raise ValueError("Pasta de envio de cancelamento não configurada")

        envia_arquivo_para_pasta(caminho_completo, industria.pasta_envio_cancelamento)

        if id_arquivo:
            # Cancelamento gerado -> fluxo encerrado.
            atualizar_status_erp_pedido(numero_pedido_ol, TipoStatusErp.PEDIDO_CANCELADO.value)

        return True
    except ErroConexaoBanco:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar cancelamento para pedido {numero_pedido_ol}: {e}")
        if id_arquivo:
            atualizar_situacao_arquivo(id_arquivo, TipoStatusOper.FALHA_CANCELAMENTO.value)
            atualizar_status_pedido(str(numero_pedido_ol), TipoStatusOper.FALHA_CANCELAMENTO.value)
        return False
