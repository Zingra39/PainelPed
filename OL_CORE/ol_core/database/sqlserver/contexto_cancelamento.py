from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.logger import logger
from ol_core.models.pedido import Pedido
from ol_core.database.sqlserver._helpers import _consultar_dataframe


# ------------------------------------------------------------------
# PEDIDO CANCELADO
# ------------------------------------------------------------------
def verifica_arquivos_cancelados(id_bbs: int, data_alvo: str) -> list[Pedido] | None:
    query = """
        select
            p.cod_pedido as cod_pedido,
            lp.nome_arquivo,
            cnpjcli.numero as Cnpj,
            p.situacao as situacao_cliente,
            lp.cod_pedido_polo as numero_pedido,
            p.digitacao as data_pedido,
            ds.cod_situacao,
            ds.definicao,
            p.data_cancelamento,
            p.quem_cancelou,
            p.faturamento,
            p.valor_total,
            p.cod_cond
        from
            log_pedido_webservice lp (NOLOCK)
            LEFT JOIN pedido p (NOLOCK) ON lp.cod_pedido = p.cod_pedido
            LEFT JOIN pedido_oper po(NOLOCK) ON p.cod_pedido = po.cod_pedido AND po.cod_operacao = 0
            LEFT JOIN def_situacao ds (NOLOCK) ON ds.cod_situacao = p.situacao
            LEFT JOIN entidade cli (NOLOCK) ON cli.cod_entidade = po.cod_entidade
            LEFT JOIN entidade_doc cnpjcli (NOLOCK) ON cnpjcli.cod_entidade = cli.cod_entidade AND cnpjcli.cod_tipo_doc = 3
        WHERE
            lp.id_opcao_atributo = :id_bbs
            AND p.data_cancelamento >= :data_alvo 
    """

    try:
        df = _consultar_dataframe(query, {"id_bbs": id_bbs, "data_alvo": data_alvo})

        if df.empty:
            return None

        df["cod_pedido"] = df["cod_pedido"].fillna(0)
        df["numero_pedido"] = df["numero_pedido"].fillna(0)

        # p.valor_total e p.cod_cond podem vir NULL do SQL Server (ex.: LEFT JOIN
        # sem match em "pedido p"). O pandas representa NULL como NaN (float) em
        # colunas numéricas, e NaN não é aceito pelo PyMySQL como parâmetro de
        # query ("nan can not be used with MySQL"). Convertendo para None aqui,
        # as checagens "is None" / "or None" já existentes em Pedido e em
        # atualizar_dados_pedido voltam a funcionar como esperado.
        df["valor_total"] = df["valor_total"].where(df["valor_total"].notna(), None)
        df["cod_cond"] = df["cod_cond"].where(df["cod_cond"].notna(), None)

        return [
            Pedido(
                nome_arquivo=row["nome_arquivo"],
                cnpj_cliente=row["Cnpj"],
                situacao_cliente=row["situacao_cliente"],
                codigo_interno_pedido=row["cod_pedido"],
                numero_pedido_ol=row["numero_pedido"],
                data_pedido=row["data_pedido"],
                cod_situacao=row["cod_situacao"],
                situacao=row["definicao"],
                data_cancelamento=row["data_cancelamento"],
                quem_cancelou=row["quem_cancelou"],
                data_faturamento=row["faturamento"],
                valor_total=row["valor_total"],
                itens=[],
                condicao=row["cod_cond"],
            )
            for _, row in df.iterrows()
        ]
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(erro)
        return None


def verifica_motivo_cancelamento(codigo_interno_pedido: int) -> str | None:
    query = """
        select
            ds.definicao
        from
            log_pedido_webservice lp (NOLOCK)
            LEFT JOIN pedido p (NOLOCK) ON lp.cod_pedido = p.cod_pedido
            LEFT JOIN def_situacao ds (NOLOCK) ON ds.cod_situacao = p.situacao
        WHERE
            p.cod_pedido = :codigo_interno_pedido
    """

    try:
        df = _consultar_dataframe(query, {"codigo_interno_pedido": codigo_interno_pedido})

        if df.empty:
            return None

        definicao = df["definicao"].values[0]
        return definicao if isinstance(definicao, str) else None
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(erro)
        return None

