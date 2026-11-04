from ol_core.core.exceptions import ErroConexaoBanco
import os
from datetime import datetime
from ol_core.database.mysql.contexto_parametros import exigir_cnpj_distribuidor
from ol_core.core.logger import logger
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.titulo import Titulo
from ol_core.models.arquivo import Arquivo
from ol_core.models.industria import Industria
from ol_core.services.conectar_ftp import envia_arquivo_ftp
from ol_core.validators.validador import valida_ean
from ol_core.models.enums.tipo_arquivo import TipoArquivo
from ol_core.utils.disparar import envia_arquivo_para_pasta
from ol_core.layouts import formato_closeup as formato
from ol_core.utils.tratamento import trata_textos
from ol_core.database.mysql.contexto_pedidos import atualizar_status_pedido, atualizar_status_erp_pedido
from ol_core.database.sqlserver.contexto_titulo import verifica_titulo_itens
from ol_core.database.mysql.contexto_arquivo import atualizar_situacao_arquivo, registrar_arquivo, verificar_espelho_existente


# Motivos do ERP (produtos_motivo) cujos itens entram no espelho; None também entra.
_MOTIVOS_NO_ESPELHO = [0, 2, 3, 19]
# Motivo informado na linha do item quando ele foi atendido parcialmente.
_MOTIVO_ATENDIMENTO_PARCIAL = 9


def gerar_espelho_closeup(industria: Industria, titulo: Titulo) -> bool:
    """Gera o arquivo ESPELHO (NF, layout Close-Up) do título, envia por FTP e
    para a pasta da indústria, e marca o pedido como "Espelho Gerado" /
    "Processo Concluído".

    Pré-condições não atendidas (pasta, nº do pedido, CNPJ) devolvem False sem
    registrar nada. Depois de registrado o arquivo, qualquer falha (exceto queda
    de banco, que sobe) marca arquivo e pedido como "Falha no Espelho"."""
    id_arquivo = None
    numero_pedido_ol = None
    try:
        pasta_output = industria.pasta_nfe
        if not pasta_output:
            logger.warning(
                f"Campo 'pasta_nfe' (pasta_espelho) não configurado para a indústria '{industria.nome}'. "
                "Configure o campo antes de gerar espelhos."
            )
            return False
        if not os.path.exists(pasta_output):os.makedirs(pasta_output)

        if titulo.numero_pedido_ol is None:
            logger.warning(f"Pedido {titulo.numero_pedido_ol} não possui número de pedido OL.")
            return False

        numero_pedido_ol = titulo.numero_pedido_ol

        if not titulo.cnpj_cliente:
            logger.warning(f"Pedido {numero_pedido_ol} não possui CNPJ do cliente.")
            return False

        cnpj_cliente = trata_textos(titulo.cnpj_cliente, 'r', 14,"0")
        if "<Error>" in cnpj_cliente:
            return False

        nome_arquivo = formato.nome_arquivo_espelho(numero_pedido_ol, cnpj_cliente)
        caminho_completo = os.path.join(pasta_output, nome_arquivo)
        id_arquivo = _reservar_arquivo_espelho(numero_pedido_ol, nome_arquivo, caminho_completo)

        data_emissao = _como_data(titulo.data_emissao)
        data_emissao.strftime("%d%m%Y")  # data inválida falha aqui, antes de consultar o distribuidor
        codigo_pedido_interno = int(titulo.codigo_pedido_interno)
        cabecalho = formato.cabecalho_espelho(
            cnpj_cliente, numero_pedido_ol, data_emissao, codigo_pedido_interno,
            _como_data(titulo.data_vencimento), exigir_cnpj_distribuidor(),
        )

        #==== VERIFICA ITENS DO PEDIDO ====
        dados_nf = formato.dados_nf_espelho(titulo.numero_titulo, titulo.serie_nf, data_emissao, titulo.chave_acesso)
        codigo_titulo = int(titulo.codigo_titulo)

        itens_registrados = verifica_titulo_itens(codigo_titulo)
        if itens_registrados is None:
            logger.warning(f"Pedido {numero_pedido_ol} não possui itens registrados")
            if id_arquivo:
                atualizar_situacao_arquivo(id_arquivo, TipoStatusOper.FALHA_ESPELHO.value)
            atualizar_status_pedido(numero_pedido_ol, TipoStatusOper.FALHA_ESPELHO.value)
            return False

        #==== DETALHES E RODAPÉ ====
        linhas_itens = []
        qtd_itens = 0
        qtd_itens_nao_atendidos = 0
        ultimo_produto_incluido = None
        for item in itens_registrados:
            if not _item_entra_no_espelho(item):
                continue
            codigo_motivo = _codigo_motivo(item)
            if _ean_longo_de_produto_repetido(item, ultimo_produto_incluido):
                continue
            linha, qtd_atendida, qtd_nao_atendido = _linha_item(item, numero_pedido_ol, dados_nf, codigo_motivo)
            ultimo_produto_incluido = item.codigo_produto
            linhas_itens.append(linha)
            qtd_itens += qtd_atendida
            qtd_itens_nao_atendidos += qtd_nao_atendido

        rodape = formato.rodape(numero_pedido_ol, len(linhas_itens) + 2, qtd_itens, qtd_itens_nao_atendidos)

        #==== CRIA E ENVIA ARQUIVO ====
        with open(caminho_completo, "w") as arquivo:
            arquivo.write(formato.conteudo_arquivo(cabecalho, linhas_itens, rodape))

        if id_arquivo:
            atualizar_situacao_arquivo(id_arquivo, TipoStatusOper.ESPELHO.value)
            atualizar_status_pedido(numero_pedido_ol, TipoStatusOper.ESPELHO.value)

        envia_arquivo_ftp('/46239901000131/ESPELHO',caminho_completo)
        logger.info(f"Espelho enviado via FTP: {nome_arquivo}")

        if not industria.pasta_envio_nf:
            raise ValueError(
                f"Campo 'pasta_envio_nf' (pasta_retorno_espelho) não configurado para a indústria '{industria.nome}'. "
                "Configure o campo antes de gerar espelhos."
            )
        envia_arquivo_para_pasta(caminho_completo, industria.pasta_envio_nf)

        if id_arquivo:
            atualizar_status_erp_pedido(numero_pedido_ol, TipoStatusErp.PROCESSO_CONCLUIDO.value)

        return True
    except ErroConexaoBanco:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar espelho para pedido {numero_pedido_ol}: {e}")
        if id_arquivo:
            atualizar_situacao_arquivo(id_arquivo, TipoStatusOper.FALHA_ESPELHO.value)
            atualizar_status_pedido(str(numero_pedido_ol), TipoStatusOper.FALHA_ESPELHO.value)
        return False


def _como_data(valor) -> datetime:
    """Datas do título vêm como datetime ou como texto "AAAA-MM-DD"."""
    if isinstance(valor, str):
        return datetime.strptime(valor, "%Y-%m-%d")
    return valor


def _reservar_arquivo_espelho(numero_pedido_ol: str, nome_arquivo: str, caminho_completo: str):
    """Registra o arquivo como "Espelho Sendo Gerado" (ou reaproveita o registro
    de um espelho anterior do pedido) e devolve o id."""
    id_arquivo = verificar_espelho_existente(numero_pedido_ol)
    if id_arquivo is None:
        arquivo_espelho = Arquivo(
            nome=nome_arquivo,
            numero_pedido_ol=numero_pedido_ol,
            caminho=caminho_completo,
            criado_em=datetime.now(),
            tipo=TipoArquivo.ESPELHO.value,
            hash="",
            situacao=TipoStatusOper.GERANDO_ESPELHO.value
        )
        return registrar_arquivo(arquivo_espelho, TipoStatusOper.GERANDO_ESPELHO.value)
    atualizar_situacao_arquivo(id_arquivo, TipoStatusOper.GERANDO_ESPELHO.value)
    return id_arquivo


def _item_entra_no_espelho(item) -> bool:
    """Fica de fora: motivo do ERP fora de _MOTIVOS_NO_ESPELHO e item sem
    quantidade atendida."""
    if item.produtos_motivo not in _MOTIVOS_NO_ESPELHO and item.produtos_motivo is not None:
        return False
    if item.quantidade_atendida == 0:
        return False
    return True


def _codigo_motivo(item) -> int:
    if item.quantidade_atendida > 0 and item.quantidade_atendida < item.quantidade_solicitada:
        return _MOTIVO_ATENDIMENTO_PARCIAL
    return 0


def _ean_longo_de_produto_repetido(item, ultimo_produto_incluido) -> bool:
    """Item com EAN de mais de 13 dígitos do mesmo produto do último item
    incluído no arquivo fica de fora, para o produto não sair repetido.

    (Antes o "último produto" nunca era atualizado e ficava sempre 0, então a
    regra só descartava itens de produto com código 0.)"""
    return len(item.ean) > 13 and item.codigo_produto == ultimo_produto_incluido


def _linha_item(item, numero_pedido_ol: str, dados_nf: str, codigo_motivo: int) -> tuple[str, int, int]:
    """Linha tipo 2 de um item. Devolve (linha, qtd atendida, qtd não atendida).
    Validação (EAN) e conversões na mesma ordem de sempre."""
    ean = valida_ean(numero_pedido_ol, item.codigo_produto, item.ean)
    qtd_atendida_int = int(item.quantidade_atendida)
    desconto = round(item.desconto,2)
    qtd_nao_atendido_int = int(item.quantidade_solicitada) - qtd_atendida_int
    valor_liquido_total = round(qtd_atendida_int * item.preco,  2)

    linha = formato.linha_item_espelho(
        ean, numero_pedido_ol, qtd_atendida_int, desconto, qtd_nao_atendido_int, codigo_motivo,
        dados_nf, valor_liquido_total,
    )
    return linha, qtd_atendida_int, qtd_nao_atendido_int
