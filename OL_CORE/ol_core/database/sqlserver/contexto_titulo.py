from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.logger import logger
from ol_core.models.titulo import Titulo
from ol_core.models.titulo_item import Titulo_Item
from ol_core.database.sqlserver._helpers import _consultar_dataframe


_TITULO_COLUMNS = """
    dbo.dv(t.cod_pedido) as codigo_pedido_interno,
    lp.nome_arquivo,
    cnpjcli.numero as cnpj_cliente,
    lp.cod_pedido_polo as numero_pedido_ol,
    t.emissao as data_emissao,
    tp.vencimento as data_vencimento,
    t.cod_titulo as codigo_titulo,
    t.numero_titulo,
    sn.serie_nf,
    ds.cod_situacao as codigo_situacao,
    t.data_cancelamento,
    p.quem_cancelou,
    t.chave_acesso
"""

_TITULO_JOINS = """
    FROM log_pedido_webservice lp (NOLOCK)
        JOIN titulo t (NOLOCK) ON t.cod_pedido = lp.cod_pedido
        LEFT JOIN serie_nf sn (NOLOCK) ON t.id_serie_nf = sn.id_serie_nf
        LEFT JOIN titulo_parcela tp(NOLOCK) ON tp.cod_titulo = t.cod_titulo and parcela = 'A'
        LEFT JOIN pedido p (NOLOCK) ON p.cod_pedido = lp.cod_pedido
        LEFT JOIN pedido_oper po(NOLOCK) ON t.cod_pedido = po.cod_pedido AND po.cod_operacao = 0
        LEFT JOIN def_situacao ds (NOLOCK) ON ds.cod_situacao = t.cod_situacao
        LEFT JOIN entidade cli (NOLOCK) ON cli.cod_entidade = po.cod_entidade
        LEFT JOIN entidade_doc cnpjcli (NOLOCK) ON cnpjcli.cod_entidade = cli.cod_entidade AND cnpjcli.cod_tipo_doc = 3
"""


def _montar_titulos(df) -> list[Titulo]:
    return [
        Titulo(
            codigo_pedido_interno=row["codigo_pedido_interno"],
            nome_arquivo=row["nome_arquivo"],
            cnpj_cliente=row["cnpj_cliente"],
            numero_pedido_ol=row["numero_pedido_ol"],
            data_emissao=row["data_emissao"],
            data_vencimento=row["data_vencimento"],
            codigo_titulo=row["codigo_titulo"],
            numero_titulo=row["numero_titulo"],
            serie_nf=row["serie_nf"],
            codigo_situacao=row["codigo_situacao"],
            data_cancelamento=row["data_cancelamento"],
            quem_cancelou=row["quem_cancelou"],
            chave_acesso=row["chave_acesso"],
        )
        for _, row in df.iterrows()
    ]


# ------------------------------------------------------------------
# TÍTULO
# ------------------------------------------------------------------
def verificar_emissao_titulos(id_bbs: int, data_alvo: str) -> list[Titulo] | None:
    query = f"""
        SELECT {_TITULO_COLUMNS}
        {_TITULO_JOINS}
        WHERE
            lp.id_opcao_atributo = :id_bbs
            AND t.emissao >= :data_alvo
    """
    try:
        df = _consultar_dataframe(query, {"id_bbs": id_bbs, "data_alvo": data_alvo})
        return None if df.empty else _montar_titulos(df)
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verificar_emissao_titulos] {erro}")
        return None


def verificar_titulo(nome_arquivo: str) -> list[Titulo] | None:
    try:
        df = _consultar_dataframe(
            f"SELECT {_TITULO_COLUMNS} {_TITULO_JOINS} WHERE LP.nome_arquivo = :nome_arquivo",
            {"nome_arquivo": nome_arquivo}
        )
        return None if df.empty else _montar_titulos(df)
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verificar_titulo] {erro}")
        return None


# ------------------------------------------------------------------
# TÍTULO ITEM
# ------------------------------------------------------------------
def verifica_titulo_itens(cod_titulo: int) -> list[Titulo_Item] | None:
    try:
        df = _consultar_dataframe(
            """
            SELECT
                ti.cod_produto as codigo_produto,
                cf.cod_barra as ean,
                pi.separado as quantidade_atendida,
                ti.pdu as desconto,
                '0' as prazo,
                pi.quantidade as quantidade_solicitada,
                pi.motivo as produtos_motivo,
                ti.preco
            FROM titulo_item ti (NOLOCK)
                LEFT JOIN titulo t (NOLOCK) ON t.cod_titulo = ti.cod_titulo
                LEFT JOIN pedido_item pi (NOLOCK) ON pi.cod_pedido = t.cod_pedido and pi.cod_produto = ti.cod_produto
                LEFT JOIN caixa_fechada cf (NOLOCK) ON cf.cod_produto = ti.cod_produto and cf.principal = -1
            WHERE ti.cod_titulo = :cod_titulo
            """,
            {"cod_titulo": cod_titulo}
        )

        if df.empty:
            return None

        df["produtos_motivo"] = df["produtos_motivo"].fillna(0)

        return [Titulo_Item(**row) for _, row in df.iterrows()]
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verifica_titulo_itens] {erro}")
        return None
