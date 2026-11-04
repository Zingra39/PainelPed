import math
from datetime import datetime, timedelta
from ol_core.core.logger import logger
from ol_core.core.conexao import buscar_um, buscar_todos, executar, executar_contando, executar_varios, inserir
from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models import regras_status
from ol_core.models.pedido import Pedido
from ol_core.models.pedido_item import Pedido_Item


# ------------------------------------------------------------------
# PEDIDO
# ------------------------------------------------------------------
def verifica_pedido_existente(nome_arquivo: str) -> bool:
    try:
        resultado = buscar_um("SELECT COUNT(*) as total FROM pedido WHERE nome_arquivo = %s", (nome_arquivo,))
        
        if resultado is not None and resultado["total"] > 0:
            return True
        
        return False
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verifica_pedido_existente] {erro}")
        return False


def inserir_pedido(id_industria: int, dados: Pedido) -> int | None:
    try:
        return inserir(
            """
            INSERT INTO pedido
                (id_industria, nome_arquivo, numero_pedido_ol, cnpj_cliente, data_pedido, observacao, valor_total, status_operacional, status_erp, criado_em, id_cond)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                id_industria, dados.nome_arquivo, dados.numero_pedido_ol, dados.cnpj_cliente, dados.data_pedido,
                dados.observacao, dados.valor_total, TipoStatusOper.IMPORTADO.value, TipoStatusErp.NAO_TRANSMITIDO.value,
                datetime.now(), dados.id_cond,
            )
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[inserir_pedido] {erro}")
        return None


def obter_id_pedido(nome_arquivo: str) -> int | None:
    try:
        resultado = buscar_um("SELECT id FROM pedido WHERE nome_arquivo = %s", (nome_arquivo,))
        return resultado["id"] if resultado else None
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[obter_id_pedido] {erro}")
        return None


def atualizar_status_pedido(numero_pedido_ol: str, status_operacional: str) -> None:
    try:
        executar(
            "UPDATE pedido SET status_operacional = %s, atualizado_em = %s WHERE numero_pedido_ol = %s",
            (status_operacional, datetime.now(), numero_pedido_ol)
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[atualizar_status_pedido] {erro}")

# Status de "geração em andamento" (regra em ol_core.models.regras_status).
# Tupla ordenada: vira a lista de parâmetros do NOT IN abaixo.
STATUS_EM_GERACAO = tuple(sorted(regras_status.EM_GERACAO))

# Uma geração leva segundos. Pedido parado em "Sendo Gerado" há mais que isto
# é de um processo que caiu no meio — a trava expira e ele volta a ser
# processável (antes, o serviço sobrescrevia o status e o recuperava).
TRAVA_GERACAO_EXPIRA = timedelta(minutes=30)


def reservar_status_pedido(numero_pedido_ol: str, novo_status: str, status_esperado: str | None = None) -> bool:
    """Troca o status_operacional numa ÚNICA instrução UPDATE condicional:
    só grava se o pedido NÃO estiver em geração (STATUS_EM_GERACAO) e, com
    `status_esperado`, só se o status atual ainda for exatamente esse. Uma
    trava de geração mais velha que TRAVA_GERACAO_EXPIRA é tratada como
    abandonada.

    Devolve True se gravou; False se a condição não valia (outro processo
    chegou antes) ou se o UPDATE falhou. Ler o status e depois gravar
    (check-then-set) deixava uma janela em que a geração manual (API) e o
    serviço automático entravam juntos e geravam o arquivo em dobro.
    """
    agora = datetime.now()
    sql = (
        "UPDATE pedido SET status_operacional = %s, atualizado_em = %s "
        "WHERE numero_pedido_ol = %s "
        "AND (status_operacional IS NULL OR status_operacional NOT IN ("
        + ", ".join(["%s"] * len(STATUS_EM_GERACAO))
        + ") OR atualizado_em < %s)"
    )
    args: list = [novo_status, agora, numero_pedido_ol, *STATUS_EM_GERACAO, agora - TRAVA_GERACAO_EXPIRA]
    if status_esperado is not None:
        sql += " AND status_operacional = %s"
        args.append(status_esperado)
    try:
        return executar_contando(sql, tuple(args)) > 0
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[reservar_status_pedido] {erro}")
        return False


def atualizar_motivo_cancelamento_pedido(numero_pedido_ol: str, motivo_cancelamento: str) -> None:
    try:
        executar(
            "UPDATE pedido SET motivo_cancelamento = %s, atualizado_em = %s WHERE numero_pedido_ol = %s",
            (motivo_cancelamento, datetime.now(), numero_pedido_ol)
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[atualizar_motivo_canclemaento_pedido] {erro}")

def atualizar_status_erp_pedido(numero_pedido_ol: str, status_erp: str) -> None:
    """Atualiza só o status_erp (coluna do ciclo de faturamento — ver
    TipoStatusErp), sem tocar em status_operacional. Chamada pelos 3
    services de geração (retorno/espelho/cancelamento_service) quando o
    respectivo arquivo é gerado com sucesso, para mover o pedido pro
    próximo estágio de faturamento (Aguardando Faturamento / Processo
    Concluido / Pedido Cancelado)."""
    try:
        executar(
            "UPDATE pedido SET status_erp = %s, atualizado_em = %s WHERE numero_pedido_ol = %s",
            (status_erp, datetime.now(), numero_pedido_ol)
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[atualizar_status_erp_pedido] {erro}")


def atualizar_transmitido_em(numero_pedido_ol: str) -> None:
    """Grava o momento da transmissão do pedido (coluna `transmitido_em`).

    Chamada junto com a marcação de status_erp = Transmitido. É a referência
    da regra que libera a geração manual do retorno após 1h sem retorno (ver
    `retorno_manual_liberado_por_atraso` em OL_API/app/services/operacoes/geracao.py).
    """
    try:
        agora = datetime.now()
        executar(
            "UPDATE pedido SET transmitido_em = %s, atualizado_em = %s WHERE numero_pedido_ol = %s",
            (agora, agora, numero_pedido_ol)
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[atualizar_transmitido_em] {erro}")


def atualizar_quantidade_atendida_itens(numero_pedido_ol: str, quantidades_por_ean: dict[str, int]) -> int:
    """Grava em `pedido_item.quantidade_atendida` as quantidades atendidas
    informadas pelo Delage (SQL Server), casando cada item do pedido pelo EAN.

    Tudo num único executemany/commit. Erro de SQL não derruba o retorno (a
    sincronização é efeito colateral): loga e devolve 0. Já a QUEDA DO BANCO
    (ErroConexaoBanco) propaga — tratá-la como "0 linhas" esconderia o
    problema.

    Retorna a quantidade de linhas de pedido_item efetivamente alteradas.
    """
    if not numero_pedido_ol or not quantidades_por_ean:
        return 0
    try:
        parametros = [
            (int(quantidade), numero_pedido_ol, ean)
            for ean, quantidade in quantidades_por_ean.items()
        ]
        return executar_varios(
            "UPDATE pedido_item SET quantidade_atendida = %s "
            "WHERE numero_pedido_ol = %s AND ean = %s",
            parametros,
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[atualizar_quantidade_atendida_itens] pedido {numero_pedido_ol}: {erro}")
        return 0


def pode_reprocessar(numero_pedido_ol: str) -> tuple[bool, str]:
    try:
        from ol_core.database.mysql.contexto_ocorrencias import buscar_ocorrencias_nao_resolvidas
        ocorrencias = buscar_ocorrencias_nao_resolvidas(numero_pedido_ol)
        if not ocorrencias:
            return True, "Nenhuma ocorrência pendente."
        severidades = {o["severidade"] for o in ocorrencias}
        return False, f"{len(ocorrencias)} ocorrência(s) pendente(s): {', '.join(severidades)}"
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[pode_reprocessar] {erro}")
        return True, "Erro ao verificar — permitindo reprocessamento."


# ------------------------------------------------------------------
# PEDIDO ITEM
# ------------------------------------------------------------------
def inserir_pedido_itens(dados: list[Pedido_Item]) -> int | None:
    """Insere todos os itens num único executemany (o pymysql monta um INSERT
    multi-linhas — uma ida ao banco em vez de uma por item). Dentro de
    `transacao()` entra no mesmo COMMIT do pedido.

    Devolve quantos itens foram inseridos, ou None em erro de SQL."""
    if not dados:
        return 0
    try:
        query = """
            INSERT INTO pedido_item
                (numero_pedido_ol, ean, codigo_produto_erp, quantidade_solicitada, quantidade_atendida, preco, desconto, cod_motivo, status, id_cond)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, 'Pendente', %s)
        """
        return executar_varios(query, [
            (
                dado.numero_pedido_ol, dado.ean, dado.codigo_produto,
                dado.quantidade_solicitada, dado.quantidade_atendida,
                dado.preco, dado.desconto, dado.cod_motivo, dado.id_cond,
            )
            for dado in dados
        ])
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[inserir_pedido_itens] {erro}")
        return None


def verificar_ean_pedido_coletado(numero_pedido: str, ean: str) -> bool:
    try:
        resultado = buscar_um(
            "SELECT COUNT(*) as total FROM pedido_item WHERE numero_pedido_ol = %s AND ean = %s",
            (numero_pedido, ean)
        )
        return resultado is not None and resultado["total"] > 0
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verificar_ean_pedido_coletado] {erro}")
        return False


def atualizar_valor_total_pedido(numero_pedido_ol: str, valor_total) -> None:
    try:
        executar(
            "UPDATE pedido SET valor_total = %s, atualizado_em = %s WHERE numero_pedido_ol = %s",
            (valor_total, datetime.now(), numero_pedido_ol)
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[atualizar_valor_total_pedido] {erro}")


def _sem_nan(valor):
    """Converte NaN (float) em None; demais valores são retornados como estão.

    Necessário porque o pandas representa valores NULL vindos do SQL Server como
    NaN (float) em colunas numéricas. Diferente de None, NaN não é aceito pelo
    PyMySQL como parâmetro de query — ele levanta
    "ValueError: nan can not be used with MySQL" ao tentar serializá-lo, o que
    faz o UPDATE inteiro falhar silenciosamente (a exceção é só logada abaixo).
    """
    if isinstance(valor, float) and math.isnan(valor):
        return None
    return valor


def atualizar_dados_pedido(pedido: Pedido, status_oper: str) -> None:
    try:
        valor_total = _sem_nan(pedido.valor_total)
        if valor_total is None:
            valor_total = 0

        codigo_interno_pedido = _sem_nan(pedido.codigo_interno_pedido) or 0
        condicao = _sem_nan(pedido.condicao)

        executar(
            """
            UPDATE pedido
            SET codigo_interno_erp = %s, valor_total = %s, condicao = %s, status_erp = %s, atualizado_em = %s
            WHERE numero_pedido_ol = %s
            """,
            # status_oper deve sempre ser TipoStatusOper.<MEMBRO>.value (nunca o membro
            # puro, nem string solta): passar o MEMBRO faz o pymysql serializar com
            # str() e gravar "TipoStatusOper.TRANSMITIDO" na coluna em vez de
            # "Transmitido" — o que quebrava a exibição no painel e, pior, a validação
            # de cancelamento em operacoes/geracao.py (_gerar_cancelamento, que compara o status_erp).
            (codigo_interno_pedido, valor_total, condicao, status_oper, datetime.now(), pedido.numero_pedido_ol)
        )
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[atualizar_dados_pedido] {erro}")


def verifica_dados_pedido(numero_pedido_ol: str) -> bool:
    try:
        resultado = buscar_um(
            "SELECT codigo_interno_erp FROM pedido WHERE numero_pedido_ol = %s",
            (numero_pedido_ol,)
        )

        if resultado is None:
            return False

        return True
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verifica_dados_pedido] {erro}")
        return False

def verificar_itens_pedido_pelo_nome_arquivo_mysql(nome_arquivo: str) -> list[Pedido_Item] | None:
    try:
        query = """
            SELECT
                pi.numero_pedido_ol,
                p.cnpj_cliente,
                pi.codigo_produto_erp AS codigo_produto,
                pi.ean,
                pi.quantidade_atendida,
                pi.quantidade_solicitada,
                pi.preco,
                pi.desconto,
                pi.id_cond,
                pi.cod_motivo
            FROM
                pedido_item pi
                INNER JOIN pedido p ON p.numero_pedido_ol = pi.numero_pedido_ol
            WHERE
                p.nome_arquivo = %s
        """

        linhas = buscar_todos(query, (nome_arquivo,))

        if not linhas:
            return None

        return [
            Pedido_Item(
                numero_pedido_ol=linha["numero_pedido_ol"] or "",
                cnpj_cliente=linha["cnpj_cliente"] or "",
                codigo_produto=linha["codigo_produto"] or 0,
                ean=linha["ean"] or "",
                quantidade_atendida=linha["quantidade_atendida"] or 0,
                quantidade_solicitada=linha["quantidade_solicitada"] or 0,
                preco=round(float(linha["preco"] or 0), 2),
                desconto=round(float(linha["desconto"] or 0), 2),
                id_cond=linha["id_cond"] or 0,
                condicao=str(linha["id_cond"]) if linha["id_cond"] is not None else "",
                cod_motivo=linha["cod_motivo"] or 0,
            )
            for linha in linhas
        ]
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verificar_itens_pedido_pelo_nome_arquivo_mysql] {erro}")
        return None
