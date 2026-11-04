from ol_core.core.exceptions import ErroConexaoBanco
import decimal
from datetime import datetime
from ol_core.models.erro import Erro, RESOLVIDO_IGNORADO
from ol_core.core.logger import logger
from ol_core.models.pedido_item import Pedido_Item
from ol_core.models.enums.tipo_severidade import TipoSeveridade
from ol_core.validators.valida_condicao import valida_condicaos
from ol_core.database.mysql.contexto_parametros import parametro_esta_ativo
from ol_core.database.mysql.contexto_ocorrencias import registrar_ocorrencia
from ol_core.database.sqlserver.contexto_produto import resgatar_produto, resgatar_produto_na_condicao, verifica_estoque_item


# Parâmetros (tela de Parametrização) que, ligados, fazem a ocorrência correspondente
# ser gravada como IGNORADO em vez de virar pendência.
PEDIDO_SEM_ITENS="PEDIDO_SEM_ITENS"
PRODUTO_NAO_CADASTRADO="PRODUTO_NAO_CADASTRADO"
PRODUTO_EM_ESTOQUE="PRODUTO_EM_ESTOQUE"
PRODUTO_ESTA_NA_CONDICAO="PRODUTO_ESTA_NA_CONDICAO"
DESCONTO_MAIOR_QUE_O_CONFIGURADO="DESCONTO_MAIOR_QUE_O_CONFIGURADO"

# Faixas da progressiva: qtd_desc_N / desc_N na condição do produto.
_FAIXAS_PROGRESSIVA = (1, 2, 3, 4)


def valida_documentacao(item: Pedido_Item):
    # [1, 10, 13, 14, 34, 36, 39, 41, 43, 45] -> Grupos que não necessitam de alvara
    # [2, 9, 10, 11, 12, 16, 40, 44] -> Precisa de alvara para medicamentos
    # [15] -> Precisa de alvara para controlados
    pass


def valida_produto(numero_ol: str, itens: list[Pedido_Item]):
    if not itens:
        _registrar(
            numero_ol, f"Pedido {numero_ol} não possui produtos.",
            TipoSeveridade.ERRO, parametro_ignorar=PEDIDO_SEM_ITENS,
        )
        return

    for item in itens:
        _valida_item(item)


def _registrar(numero_pedido_ol, descricao: str, severidade: TipoSeveridade, parametro_ignorar: str | None = None) -> None:
    """Grava a ocorrência. Se ela tem parâmetro de ignorar e ele está ligado,
    vai como IGNORADO (não conta como pendência)."""
    erro = Erro(
        numero_pedido_ol=numero_pedido_ol,
        descricao=descricao,
        criado_em=datetime.now(),
        severidade=severidade.value,
        resolvido=0
    )
    if parametro_ignorar and parametro_esta_ativo(parametro_ignorar):
        erro.resolvido = RESOLVIDO_IGNORADO
        erro.severidade = TipoSeveridade.IGNORADO.value
    registrar_ocorrencia(erro)


def _valida_item(item: Pedido_Item) -> None:
    """Valida um item. Erro inesperado vira ocorrência CRÍTICA do item, sem
    interromper os demais; queda de banco sobe."""
    try:
        produto = resgatar_produto(item.ean)

        valida_condicaos(item.id_cond, item.cnpj_cliente, item.numero_pedido_ol)

        if not produto:
            _registrar(
                item.numero_pedido_ol, f"Produto não está cadastrado no Delage: {item.ean}",
                TipoSeveridade.ERRO, parametro_ignorar=PRODUTO_NAO_CADASTRADO,
            )
            return

        valida_documentacao(item)

        if verifica_estoque_item(produto['codigo_produto']):
            _registrar(
                item.numero_pedido_ol, f"Produto não está em estoque: {item.ean}",
                TipoSeveridade.INFO, parametro_ignorar=PRODUTO_EM_ESTOQUE,
            )

        produto_condicao = resgatar_produto_na_condicao(item.codigo_produto, item.id_cond)
        if not produto_condicao:
            _registrar(
                item.numero_pedido_ol, f"Produto não está configurado na condição: {item.ean}",
                TipoSeveridade.ALERTA, parametro_ignorar=PRODUTO_ESTA_NA_CONDICAO,
            )
            return

        # Progressiva só vale quando o desconto não foi negociado.
        if produto_condicao['desconto_negociado'] == 0:
            _valida_progressiva(item, produto, produto_condicao)

        _valida_desconto_maximo(item, produto, produto_condicao)
    except ErroConexaoBanco:
        raise
    except Exception as err:
        logger.error(f"Erro ao validar produto {item}: {err}")
        _registrar(item.numero_pedido_ol, f"Erro ao validar EAN {item.ean}", TipoSeveridade.CRITICO)


def _descricao_desconto_acima(produto, item: Pedido_Item, aplicado, limite) -> str:
    # Vírgula decimal só nos percentuais — a descrição do produto e o EAN saem
    # como estão no cadastro (antes o "." era trocado na mensagem inteira).
    aplicado = str(aplicado).replace('.', ',')
    limite = str(limite).replace('.', ',')
    return (
        f"Desconto do {produto['descricao']} - {item.ean} maior que o configurado na condicao "
        f"(aplicado: {aplicado}%, limite: {limite}%)"
    )


def _valida_progressiva(item: Pedido_Item, produto, produto_condicao) -> None:
    """Desconto progressivo por quantidade: a faixa N vale de qtd_desc_N até a
    próxima faixa configurada; o desconto do item não pode passar de desc_N.
    Atingir a faixa é por quantidade atendida OU solicitada. Faixa com
    qtd_desc_N = 0 não está configurada (exceto a 1, que liga a progressiva)."""
    if produto_condicao['qtd_desc_1'] == 0:
        return

    qtd_atend = item.quantidade_atendida
    qtd_solic = item.quantidade_solicitada

    def atinge(faixa: int) -> bool:
        minimo = produto_condicao[f'qtd_desc_{faixa}']
        return qtd_atend >= minimo or qtd_solic >= minimo

    na_faixa = {1: atinge(1)}
    for faixa in _FAIXAS_PROGRESSIVA[1:]:
        na_faixa[faixa] = produto_condicao[f'qtd_desc_{faixa}'] != 0 and atinge(faixa)

    if not na_faixa[1]:
        _registrar(
            item.numero_pedido_ol,
            f"Quantidade do {produto['descricao']} - {item.ean} menor que o configurado na condicao",
            TipoSeveridade.ALERTA,
        )
        return

    for faixa in _FAIXAS_PROGRESSIVA:
        atinge_a_proxima = na_faixa.get(faixa + 1, False)
        if na_faixa[faixa] and not atinge_a_proxima:
            limite = produto_condicao[f'desc_{faixa}']
            if item.desconto > limite:
                _registrar(
                    item.numero_pedido_ol,
                    _descricao_desconto_acima(produto, item, f"{item.desconto:.2f}", f"{limite:.2f}"),
                    TipoSeveridade.ALERTA,
                )


def _valida_desconto_maximo(item: Pedido_Item, produto, produto_condicao) -> None:
    """Desconto do arquivo não pode passar do desconto da condição (comparado
    com 2 casas). Desconto 0 na condição = sem teto."""
    if produto_condicao['desconto'] == 0:
        return

    desconto_condicao = decimal.Decimal(produto_condicao['desconto'] or 0).quantize(decimal.Decimal('0.01'))
    desconto_item_pedido = decimal.Decimal(item.desconto).quantize(decimal.Decimal('0.01'))

    if desconto_item_pedido > desconto_condicao:
        _registrar(
            item.numero_pedido_ol,
            _descricao_desconto_acima(produto, item, desconto_item_pedido, desconto_condicao),
            TipoSeveridade.ALERTA, parametro_ignorar=DESCONTO_MAIOR_QUE_O_CONFIGURADO,
        )
