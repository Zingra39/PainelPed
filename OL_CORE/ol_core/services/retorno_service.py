from ol_core.core.exceptions import ErroConexaoBanco
import os
from datetime import datetime
from ol_core.database.mysql.contexto_parametros import exigir_cnpj_distribuidor
from ol_core.core.logger import logger
from ol_core.models.pedido import Pedido
from ol_core.models.arquivo import Arquivo
from ol_core.models.industria import Industria
from ol_core.models.pedido_item import Pedido_Item
from ol_core.models.enums.tipo_arquivo import TipoArquivo
from ol_core.utils.disparar import envia_arquivo_para_pasta
from ol_core.services.conectar_ftp import envia_arquivo_ftp
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.layouts import formato_closeup as formato
from ol_core.validators.validador import valida_motivo, valida_ean
from ol_core.utils.tratamento import trata_textos
from ol_core.database.mysql.contexto_pedidos import atualizar_status_pedido, atualizar_status_erp_pedido, atualizar_quantidade_atendida_itens
from ol_core.database.mysql.contexto_pedidos import verificar_itens_pedido_pelo_nome_arquivo_mysql
from ol_core.database.sqlserver.contexto_pedido import verifica_todos_eans_itens_pedido_pelo_nome_arquivo
from ol_core.database.mysql.contexto_ocorrencias import marcar_ocorrencias_resolvidas, marcar_ocorrencias_item_resolvidas
from ol_core.database.mysql.contexto_arquivo import atualizar_situacao_arquivo, registrar_arquivo, verificar_retorno_existente
from ol_core.services.merge_itens_pedido import combinar_itens_sql_e_mysql



def _sincronizar_quantidade_atendida(
    itens_sql: list[Pedido_Item] | None,
    itens_mysql: list[Pedido_Item] | None,
) -> None:
    """Atualiza `pedido_item.quantidade_atendida` (MySQL/painel) com a
    quantidade atendida que o Delage (SQL Server, coluna `pedido_item.separado`)
    informa para o mesmo item.

    Roda na etapa de verificação dos itens do retorno. Regras:
    - O casamento é por EAN, a mesma chave do merge (`combinar_itens_sql_e_mysql`).
      Item sem EAN em comum entre as fontes não é tocado — sem casamento seguro,
      não se grava quantidade.
    - Só grava o que mudou.
    - EAN com mais de uma linha no Delage e quantidades diferentes é ambíguo
      (mesmo produto em mais de uma linha do pedido): pula e avisa no log.
    - Sem itens em uma das fontes (ex.: Delage sem o item), não há o que sincronizar.
    - Nunca levanta exceção: falha aqui não pode virar "Falha no Retorno".
    """
    try:
        if not itens_sql or not itens_mysql:
            return

        quantidades_sql: dict[str, set[int]] = {}
        for item in itens_sql:
            if item.ean:
                quantidades_sql.setdefault(item.ean, set()).add(int(item.quantidade_atendida or 0))

        quantidades_novas: dict[str, int] = {}
        for item in itens_mysql:
            quantidades = quantidades_sql.get(item.ean)
            if not quantidades:
                continue
            if len(quantidades) > 1:
                logger.warning(
                    f"EAN {item.ean} do pedido {item.numero_pedido_ol} tem quantidades atendidas "
                    f"diferentes no Delage {sorted(quantidades)} — quantidade atendida não sincronizada."
                )
                continue
            quantidade = next(iter(quantidades))
            if quantidade != int(item.quantidade_atendida or 0):
                quantidades_novas[item.ean] = quantidade

        numero_pedido_ol = next((i.numero_pedido_ol for i in itens_mysql if i.numero_pedido_ol), None)
        if quantidades_novas and numero_pedido_ol:
            atualizar_quantidade_atendida_itens(numero_pedido_ol, quantidades_novas)
    except ErroConexaoBanco:
        raise
    except Exception as error:
        logger.error(f"[_sincronizar_quantidade_atendida] {error}")


def verificar_itens_pedido(nome_pedido: str) -> list[Pedido_Item]:
    """Busca os itens do pedido combinando Delage (SQL Server) e MySQL (painel).

    Quando um item existe nas duas fontes, prevalece a versão do SQL Server —
    fonte mais atualizada/oficial. Quando o Delage não tem NENHUM item pro
    pedido (ex.: produto não cadastrado lá, então o Delage nunca criou a linha
    do item), cai integralmente pros dados do MySQL, em vez de devolver lista
    vazia e forçar Falha no Retorno — o painel já tem os dados originais do
    pedido (ean, quantidade, desconto etc.), não há motivo pra descartá-los só
    porque o Delage não processou o item (achado: pedido 2026091000328692172P,
    produto 7896094933071 não cadastrado no Delage).
    """
    try:
        df_itens_sql = verifica_todos_eans_itens_pedido_pelo_nome_arquivo(nome_pedido)
        df_itens_mysql = verificar_itens_pedido_pelo_nome_arquivo_mysql(nome_pedido)

        # Aproveita a verificação para refletir no painel o que o Delage atendeu.
        _sincronizar_quantidade_atendida(df_itens_sql, df_itens_mysql)

        if not df_itens_sql and df_itens_mysql:
            logger.warning(
                f"Pedido do arquivo {nome_pedido} sem itens no Delage — "
                "usando os itens do MySQL (painel) como origem."
            )

        return combinar_itens_sql_e_mysql(df_itens_sql, df_itens_mysql)
    except ErroConexaoBanco:
        raise
    except Exception as error:
        logger.error(error)
        return []

def gerar_retorno_closeup(industria: Industria, pedido: Pedido) -> bool:
    """Gera o arquivo de RETORNO (layout Close-Up), envia por FTP e para a pasta
    da indústria, e marca arquivo/pedido como "Retorno Gerado".

    Aqui ficam os dados, as validações e a entrega; o texto de cada linha
    (posições e larguras) vem de ol_core.layouts.formato_closeup.

    Qualquer falha (exceto queda de banco, que sobe) marca arquivo e pedido
    como "Falha no Retorno" e devolve False."""
    id_arquivo = None
    numero_pedido_ol = None
    try:
        pasta_output = industria.pasta_retorno
        if not pasta_output:
            raise ValueError("Pasta de retorno não informada")

        numero_pedido_ol = pedido.numero_pedido_ol
        if not numero_pedido_ol:
            raise ValueError("Número do pedido não informado")

        cnpj_cliente = _cnpj_cliente(pedido)
        if cnpj_cliente == "<Error>":
            return False

        nome_arquivo = formato.nome_arquivo_retorno(numero_pedido_ol, cnpj_cliente)
        caminho_completo = os.path.join(pasta_output, nome_arquivo)
        id_arquivo = _reservar_arquivo_retorno(numero_pedido_ol, nome_arquivo, caminho_completo)

        codigo_interno_pedido = pedido.codigo_interno_pedido or 0
        cabecalho = formato.cabecalho_retorno(
            cnpj_cliente, numero_pedido_ol, _data_processamento(pedido), codigo_interno_pedido,
            exigir_cnpj_distribuidor(),
        )

        #==== VERIFICA ITENS DO PEDIDO ====
        if not codigo_interno_pedido and pedido.data_pedido:
            logger.warning(f"Pedido {numero_pedido_ol} sem codigo_interno_pedido — não é possível buscar os itens no ERP")
            _marcar_falha_retorno(id_arquivo, numero_pedido_ol)
            return False

        if not pedido.nome_arquivo:
            logger.warning(f"Pedido {numero_pedido_ol} sem nome_arquivo — não é possível buscar os itens no ERP")
            _marcar_falha_retorno(id_arquivo, numero_pedido_ol)
            return False

        pedido_itens = verificar_itens_pedido(pedido.nome_arquivo)
        if len(pedido_itens) == 0:
            logger.warning(f"Pedido {numero_pedido_ol} não possui itens registrados")
            _marcar_falha_retorno(id_arquivo, numero_pedido_ol)
            return False

        #==== DETALHES E RODAPÉ ====
        linhas_itens = []
        qtd_total_atendidos = 0
        qtd_total_nao_atendidos = 0
        for item in pedido_itens:
            linha, qtd_atendida, qtd_nao_atendido = _linha_item(item, pedido, numero_pedido_ol, cnpj_cliente)
            linhas_itens.append(linha)
            qtd_total_atendidos += qtd_atendida
            qtd_total_nao_atendidos += qtd_nao_atendido

        rodape = formato.rodape(numero_pedido_ol, len(linhas_itens) + 2, qtd_total_atendidos, qtd_total_nao_atendidos)

        #==== CRIA E ENVIA ARQUIVO ====
        with open(caminho_completo, "w") as arquivo:
            arquivo.write(formato.conteudo_arquivo(cabecalho, linhas_itens, rodape))

        envia_arquivo_ftp('/46239901000131/RETORNO',caminho_completo)
        logger.info(f"Retorno enviado via FTP: {nome_arquivo}")

        if not industria.pasta_envio_retorno:
            logger.warning(f"Industria {industria.nome} sem pasta de envio de retorno — não é possível enviar o arquivo")
            _marcar_falha_retorno(id_arquivo, numero_pedido_ol)
            return False

        envia_arquivo_para_pasta(caminho_completo, industria.pasta_envio_retorno)

        atualizar_situacao_arquivo(id_arquivo, TipoStatusOper.RETORNO.value)
        atualizar_status_pedido(numero_pedido_ol, TipoStatusOper.RETORNO.value)
        # Retorno gerado -> pedido aguarda faturamento (Espelho) ou Cancelamento.
        atualizar_status_erp_pedido(numero_pedido_ol, TipoStatusErp.AGUARDANDO_FATURAMENTO.value)

        marcar_ocorrencias_resolvidas(numero_pedido_ol)
        marcar_ocorrencias_item_resolvidas(numero_pedido_ol)

        return True
    except ErroConexaoBanco:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar retorno para pedido {numero_pedido_ol}: {e}")
        _marcar_falha_retorno(id_arquivo, numero_pedido_ol)
        return False


def _marcar_falha_retorno(id_arquivo, numero_pedido_ol) -> None:
    if id_arquivo:
        atualizar_situacao_arquivo(id_arquivo, TipoStatusOper.FALHA_RETORNO.value)
    if numero_pedido_ol:
        atualizar_status_pedido(numero_pedido_ol, TipoStatusOper.FALHA_RETORNO.value)


def _cnpj_cliente(pedido: Pedido) -> str:
    """CNPJ do cliente com 14 dígitos. Sem CNPJ no pedido, sai do nome do
    arquivo. Devolve "<Error>" se o CNPJ for inválido."""
    if pedido.cnpj_cliente:
        return trata_textos(pedido.cnpj_cliente, 'r', 14,"0")
    nome_arquivo = os.path.basename(pedido.nome_arquivo) if pedido.nome_arquivo else ""
    cnpj = formato.cnpj_do_nome_arquivo(nome_arquivo)
    if cnpj is None:
        raise ValueError(f"Pedido sem CNPJ do cliente e nome de arquivo sem CNPJ: '{nome_arquivo}'")
    return cnpj


def _data_processamento(pedido: Pedido) -> datetime:
    """Data do pedido (ou agora, se o pedido não tiver data)."""
    if pedido.data_pedido and isinstance(pedido.data_pedido, datetime):
        return pedido.data_pedido
    return datetime.now()


def _reservar_arquivo_retorno(numero_pedido_ol: str, nome_arquivo: str, caminho_completo: str):
    """Registra o arquivo como "Retorno Sendo Gerado" (ou reaproveita o registro
    de um retorno anterior do pedido) e devolve o id."""
    id_arquivo = verificar_retorno_existente(numero_pedido_ol)
    if id_arquivo is None:
        arquivo_retorno = Arquivo(
            nome=nome_arquivo,
            numero_pedido_ol=numero_pedido_ol,
            caminho=caminho_completo,
            criado_em=datetime.now(),
            tipo=TipoArquivo.RETORNO.value,
            hash="",
            situacao=TipoStatusOper.GERANDO_RETORNO.value
        )
        return registrar_arquivo(arquivo_retorno, TipoStatusOper.GERANDO_RETORNO.value)
    atualizar_situacao_arquivo(id_arquivo, TipoStatusOper.GERANDO_RETORNO.value)
    return id_arquivo


def _linha_item(item: Pedido_Item, pedido: Pedido, numero_pedido_ol: str, cnpj_cliente: str) -> tuple[str, int, int]:
    """Linha tipo 2 de um item. Devolve (linha, qtd atendida, qtd não atendida).
    Validações (EAN, motivo) e conversões na mesma ordem de sempre."""
    ean = valida_ean(numero_pedido_ol, item.codigo_produto, item.ean)
    qtd_atendida = int(item.quantidade_atendida)
    desconto = round(item.desconto,2)
    qtd_nao_atendido = int(item.quantidade_solicitada) - qtd_atendida
    cod_motivo = valida_motivo(item, pedido, cnpj_cliente)

    linha = formato.linha_item_retorno(ean, numero_pedido_ol, qtd_atendida, desconto, qtd_nao_atendido, cod_motivo)
    return linha, qtd_atendida, qtd_nao_atendido
