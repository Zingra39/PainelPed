from ol_core.core.exceptions import ErroConexaoBanco
from sqlalchemy import text
from ol_core.core.logger import logger
from ol_core.core.conexao import obter_engine_erp
from ol_core.database.sqlserver._helpers import _consultar_dataframe
from ol_core.utils.cnpj import parametros_cnpj


# ------------------------------------------------------------------
# CLIENTE
# ------------------------------------------------------------------
def resgatar_cliente(cnpj: str) -> dict | None:
    try:
        engine = obter_engine_erp()
        with engine.connect() as conn:
            resultado = conn.execute(
                text("""
                    SELECT
                        e.cod_entidade      AS codigo_entidade,
                        e.razao_social,
                        e.fantasia,
                        ed.DocSemMasc       AS cnpj,
                        ed3.numero          AS numero_alvara,
                        ed3.vencimento      AS vencimento_alvara,
                        ds.descricao        AS situacao_entidade
                    FROM entidade e (NOLOCK)
                        LEFT JOIN vw_entidade_doc ed  (NOLOCK) ON e.cod_entidade = ed.cod_entidade  AND ed.cod_tipo_doc  = 3
                        LEFT JOIN vw_entidade_doc ed3 (NOLOCK) ON e.cod_entidade = ed3.cod_entidade AND ed3.cod_tipo_doc = 5
                        LEFT JOIN def_situacao_entidade ds (NOLOCK) ON e.situacao = ds.cod_situacao
                    WHERE ed.DocSemMasc = :cnpj
                """),
                {"cnpj": cnpj}
            ).fetchone()

        if not resultado:
            return None

        return {
            "codigo_entidade":   resultado[0],
            "razao_social":      resultado[1],
            "fantasia":          resultado[2],
            "cnpj":              resultado[3],
            "numero_alvara":     resultado[4],
            "vencimento_alvara": resultado[5],
            "situacao_entidade": resultado[6],
        }
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[resgatar_cliente] CNPJ={cnpj} — {erro}")
        return None


# ------------------------------------------------------------------
# CONDIÇÃO
# ------------------------------------------------------------------
def resgatar_condicao(id_condicao: int) -> dict | None:
    try:
        engine = obter_engine_erp()
        with engine.connect() as conn:
            resultado = conn.execute(
                text("""
                    SELECT
                        c.id_cond,
                        c.cod_cond,
                        c.acessa_outras_cond,
                        c.acessivel_outras_cond,
                        c.todos_clientes,
                        c.BBS,
                        c.final,
                        c.maximo,
                        c.pri_min_valor
                    FROM cond c (NOLOCK)
                    WHERE c.id_cond = :id_condicao
                """),
                {"id_condicao": id_condicao}
            ).fetchone()

        if not resultado:
            return None

        return {
            "id_cond":               resultado[0] or 0,
            "cod_cond":              resultado[1] or None,
            "acessa_outras_cond":    resultado[2] or None,
            "acessivel_outras_cond": resultado[3] or None,
            "todos_clientes":        resultado[4] or None,
            "bbs":                   resultado[5] or None,
            "validade_condicao":     resultado[6] or None,
            "desconto_negociado":    resultado[7] or 0.00,
            "valor_minimo_pedido":   round(resultado[8] or 0, 2),
        }
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[resgatar_condicao] cond={id_condicao} — {erro}")
        return None


def verificar_condicao(condicao: str):
    try:
        df = _consultar_dataframe(
            """
            SELECT c.todos_clientes, c.final, c.pri_min_valor, c.BBS
            FROM cond C (NOLOCK)
            WHERE c.cod_cond = :condicao
            """,
            {"condicao": condicao}
        )
        return None if df.empty else df.iloc[0]
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verificar_condicao] {erro}")


def verifica_cliente_na_condicao(condicao: str, cnpj: str) -> bool | None:
    try:
        df = _consultar_dataframe(
            """
                SELECT COUNT(*) AS total
                FROM cond_cliente cc (NOLOCK)
                    LEFT JOIN entidade_doc ed (NOLOCK)
                        ON ed.cod_entidade = cc.cod_entidade
                        AND ed.cod_tipo_doc = 3
                WHERE cc.cod_cond = :condicao
                AND ed.numero IN (:cnpj, :cnpj_mascarado)
            """,
            # Sem dbo.RetiraEspacos_E_CatacteresEspeciais na coluna: a máscara
            # é aplicada no parâmetro (ver ol_core/utils/cnpj.py).
            {"condicao": condicao, **parametros_cnpj(cnpj)}
        )
        
        if df.empty or df.iloc[0]["total"] == 0:
            return False
        
        return df.iloc[0]["total"] > 0
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verifica_cliente_na_condicao] {erro}")
        return None


def verificar_item_condicao(codigo_produto: int, condicao: str):
    try:
        df = _consultar_dataframe(
            """
                SELECT
                    cp.preco, cp.desconto,
                    cp.qtd_desc_1, cp.desc_1,
                    cp.qtd_desc_2, cp.desc_2,
                    cp.qtd_desc_3, cp.desc_3,
                    cp.qtd_desc_4, cp.desc_4
                FROM cond_prod cp (NOLOCK)
                WHERE cp.cod_produto = :cod_produto
                AND cp.cod_cond = :cod_condicao
            """,
            {"cod_produto": codigo_produto, "cod_condicao": condicao}
        )
        if df.empty:
            return None
        return df.round(2).iloc[0]
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verificar_item_condicao] {erro}")
