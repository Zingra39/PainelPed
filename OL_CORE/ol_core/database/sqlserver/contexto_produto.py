from ol_core.core.exceptions import ErroConexaoBanco
from sqlalchemy import text
from ol_core.core.logger import logger
from ol_core.core.conexao import obter_engine_erp
from ol_core.database.sqlserver._helpers import _consultar_dataframe
from ol_core.database.mysql.contexto_parametros import filiais_estoque


# ------------------------------------------------------------------
# FILIAIS DE ESTOQUE
# ------------------------------------------------------------------
# Antes: `cod_filial = 12328` fixo no SQL. Agora as filiais vêm da tela de
# Parametrização (parâmetro `filiais_estoque`); o estoque considerado é a SOMA
# das filiais configuradas. Sem filial configurada, não há filtro: soma todas.
def _filtro_filiais(coluna: str) -> tuple[str, dict]:
    """Trecho ` AND <coluna> IN (:filial_0, ...)` e seus parâmetros — ou
    trecho vazio, se nenhuma filial estiver configurada."""
    filiais = filiais_estoque()
    if not filiais:
        return "", {}
    nomes = [f"filial_{i}" for i in range(len(filiais))]
    trecho = f" AND {coluna} IN ({', '.join(':' + n for n in nomes)})"
    return trecho, dict(zip(nomes, filiais))


def _estoque_por_produto(coluna_produto: str) -> tuple[str, dict]:
    """OUTER APPLY com o estoque do produto somado nas filiais configuradas
    (exposto como `que.estoque`, NULL se não houver linha de estoque)."""
    filtro, params = _filtro_filiais("e.cod_filial")
    trecho = f"""
        OUTER APPLY (
            SELECT SUM(e.estoque) AS estoque
            FROM dbo.produto_estoque e (NOLOCK)
            WHERE e.cod_produto = {coluna_produto}{filtro}
        ) que"""
    return trecho, params


# ------------------------------------------------------------------
# PRODUTO
# ------------------------------------------------------------------
def resgatar_produto(ean: str) -> dict | None:
    try:
        estoque_sql, estoque_params = _estoque_por_produto("prod.cod_produto")
        engine = obter_engine_erp()
        with engine.connect() as conn:
            resultado = conn.execute(
                text(f"""
                    SELECT
                        prod.descricao,
                        prod.preco,
                        dbo.dv(prod.cod_produto)    AS codigo_produto,
                        ds.DESCRICAO         AS situacao_produto,
                        prod.desconto,
                        cf.cod_barra         AS ean,
                        que.estoque,
                        cf.principal
                    FROM produto prod (NOLOCK)
                        LEFT JOIN def_situacao_produto ds  (NOLOCK) ON ds.cod_situacao = prod.situacao
                        LEFT JOIN caixa_fechada        cf  (NOLOCK) ON cf.cod_produto  = prod.cod_produto
                        {estoque_sql}
                    WHERE cf.cod_barra = :ean
                """),
                {"ean": ean, **estoque_params}
            ).fetchone()

        if not resultado:
            return None

        # Considera 0 para os campos None
        resultado = [0 if i is None else i for i in resultado]

        return {
            "descricao":      resultado[0],
            "preco":          round(resultado[1], 2),
            "codigo_produto": resultado[2],
            "situacao":       resultado[3],
            "desconto":       resultado[4],
            "ean":            resultado[5],
            "estoque":        resultado[6],
            "principal":      resultado[7],
        }
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[resgatar_produto] EAN={ean} — {erro}")
        return None


def resgatar_produtos_por_lote(eans: list[str]) -> list[dict]:
    """Retorna lista de produtos para todos os EANs de uma vez."""
    if not eans:
        return []
    placeholders = ", ".join(f":ean_{i}" for i, _ in enumerate(eans))
    params = {f"ean_{i}": ean for i, ean in enumerate(eans)}
    try:
        estoque_sql, estoque_params = _estoque_por_produto("prod.cod_produto")
        params.update(estoque_params)
        engine = obter_engine_erp()
        with engine.connect() as conn:
            rows = conn.execute(text(f"""
                SELECT
                    prod.descricao,
                    prod.preco,
                    dbo.dv(prod.cod_produto) AS codigo_produto,
                    ds.DESCRICAO AS situacao_produto,
                    prod.desconto,
                    cf.cod_barra AS ean,
                    que.estoque,
                    cf.principal
                FROM
                    produto prod (NOLOCK)
                    LEFT JOIN def_situacao_produto ds  (NOLOCK) ON ds.cod_situacao = prod.situacao
                    LEFT JOIN caixa_fechada        cf  (NOLOCK) ON cf.cod_produto  = prod.cod_produto
                    {estoque_sql}
                WHERE
                    cf.cod_barra IN ({placeholders})
            """), params).fetchall()
        return [
            {
                "descricao": row[0],
                "preco": round(row[1], 2),
                "codigo_produto": row[2],
                "situacao": row[3],
                "desconto": row[4],
                "ean": row[5],
                "estoque": row[6],
                "principal": row[7],
            }
            for row in rows
        ]
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[resgatar_produtos_em_lote] {erro}")
        return []


def resgatar_produto_na_condicao(codigo_produto: int, id_condicao: int) -> dict | None:
    try:
        engine = obter_engine_erp()
        with engine.connect() as conn:
            resultado = conn.execute(
                text("""
                    SELECT
                        c.id_cond,
                        c.cod_cond,
                        cp.desconto,
                        cp.preco,
                        dbo.dv(cp.cod_produto)          AS codigo_produto,
                        c.maximo                AS desconto_negociado,
                        cp.qtd_desc_1, cp.desc_1,
                        cp.qtd_desc_2, cp.desc_2,
                        cp.qtd_desc_3, cp.desc_3,
                        cp.qtd_desc_4, cp.desc_4,
                        cp.qtd_desc_5, cp.desc_5
                    FROM cond c (NOLOCK)
                        LEFT JOIN cond_prod cp (NOLOCK) ON c.cod_cond = cp.cod_cond AND dbo.dv(cp.cod_produto) = :codigo_produto
                    WHERE c.id_cond = :id_condicao
                """),
                {"codigo_produto": codigo_produto, "id_condicao": id_condicao}
            ).fetchone()

        if not resultado:
            return None

        resultado = [0 if i is None else i for i in resultado]

        def _r(v):
            return round(v, 2) if v is not None else 0

        return {
            "id_cond":            resultado[0],
            "cod_cond":           resultado[1],
            "desconto":           _r(resultado[2]),
            "preco":              _r(resultado[3]),
            "codigo_produto":     resultado[4],
            "desconto_negociado": resultado[5],
            "qtd_desc_1": resultado[6],  "desc_1": _r(resultado[7]),
            "qtd_desc_2": resultado[8],  "desc_2": _r(resultado[9]),
            "qtd_desc_3": resultado[10], "desc_3": _r(resultado[11]),
            "qtd_desc_4": resultado[12], "desc_4": _r(resultado[13]),
            "qtd_desc_5": resultado[14], "desc_5": _r(resultado[15]),
        }
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[resgatar_produto_na_condicao] produto={codigo_produto} cond={id_condicao} — {erro}")
        return None


def resgata_classificao(ean: str) -> int:
    try:
        engine = obter_engine_erp()
        with engine.connect() as conn:
            resultado = conn.execute(
                text("""
                    SELECT	
                        grupo.id_grupo
                    FROM
                        produto p (NOLOCK)
                        LEFT JOIN caixa_fechada cf (NOLOCK) ON cf.cod_produto = p.cod_produto
                        LEFT JOIN dbo.vw_RS_grupo_produto grupo (NOLOCK) ON p.grupo = grupo.id_subgrupo
                    WHERE
                        cf.cod_barra = :ean
                    ORDER BY
                        grupo.id_grupo
                """),
                {"ean": ean}
            ).fetchone()
        return resultado[0] if resultado else 0
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[resgata_classificao] EAN={ean} — {erro}")
        return 0

# ------------------------------------------------------------------
# EAN / ESTOQUE
# ------------------------------------------------------------------
def verifica_tipo_ean(cod_produto: int):
    try:
        df = _consultar_dataframe(
            "SELECT cod_barra as ean FROM caixa_fechada (NOLOCK) WHERE cod_produto = :cod_produto AND tipo_cod_barra = 1",
            {"cod_produto": cod_produto}
        )
        return None if df.empty else df["ean"]
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verifica_tipo_ean] {erro}")


def verifica_primeiro_ean_valido(cod_produto: int) -> str | None:
    try:
        df = _consultar_dataframe(
            "SELECT cod_barra as ean FROM caixa_fechada (NOLOCK) WHERE cod_produto = :cod_produto AND tipo_cod_barra = 1",
            {"cod_produto": cod_produto}
        )
        return None if df.empty else df.iloc[0]["ean"]
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verifica_primeiro_ean_valido] {erro}")


def verifica_estoque_item(codigo_produto: int) -> bool | None:
    try:
        filtro, params = _filtro_filiais("que.cod_filial")
        # HAVING: sem nenhuma linha de estoque a consulta volta vazia (None),
        # como antes — e não uma soma NULL.
        df = _consultar_dataframe(
            "SELECT SUM(que.estoque - que.retencao) as estoque FROM dbo.produto_estoque que (NOLOCK) "
            f"WHERE dbo.dv(que.cod_produto) = :cod_produto{filtro} HAVING COUNT(*) > 0",
            {"cod_produto": codigo_produto, **params}
        )
        return None if df.empty else df.iloc[0]["estoque"] == 0
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verifica_estoque_item] {erro}")


def verifica_estoque_item_pedido(codigo_produto: int) -> bool | None:
    """Mesma checagem de verifica_estoque_item, mas para o cod_produto bruto de pedido_item (sem dbo.dv())."""
    try:
        filtro, params = _filtro_filiais("que.cod_filial")
        # HAVING: sem nenhuma linha de estoque a consulta volta vazia (None),
        # como antes — e não uma soma NULL.
        df = _consultar_dataframe(
            "SELECT SUM(que.estoque - que.retencao) as estoque FROM dbo.produto_estoque que (NOLOCK) "
            f"WHERE que.cod_produto = :cod_produto{filtro} HAVING COUNT(*) > 0",
            {"cod_produto": codigo_produto, **params}
        )
        return None if df.empty else df.iloc[0]["estoque"] == 0
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verifica_estoque_item_pedido] {erro}")


def verifica_quantidade_que_sera_atendida(codigo_produto: int):
    try:
        filtro, params = _filtro_filiais("que.cod_filial")
        # HAVING: sem nenhuma linha de estoque a consulta volta vazia (None),
        # como antes — e não uma soma NULL.
        df = _consultar_dataframe(
            "SELECT SUM(que.estoque - que.retencao) as estoque FROM dbo.produto_estoque que (NOLOCK) "
            f"WHERE dbo.dv(que.cod_produto) = :cod_produto{filtro} HAVING COUNT(*) > 0",
            {"cod_produto": codigo_produto, **params}
        )
        return None if df.empty else df.iloc[0]["estoque"]
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verifica_quantidade_que_sera_atendida] {erro}")


def resgata_estoque(fornecedores: list[int]):
    """Estoque disponível dos produtos dos fornecedores informados (códigos do
    fornecedor no ERP, cadastrados na indústria), somado nas filiais
    configuradas. Sem fornecedor devolve None: sem esse filtro o arquivo
    levaria o estoque de todos os produtos do ERP para a indústria."""
    if not fornecedores:
        logger.error("[resgata_estoque] Nenhum código de fornecedor informado — consulta não executada.")
        return None

    nomes = [f"fornecedor_{i}" for i in range(len(fornecedores))]
    params = dict(zip(nomes, fornecedores))
    filtro_filial, params_filial = _filtro_filiais("est.id_filial")
    params.update(params_filial)

    query = f"""
        select
            vwp.descricao as Descricao,
            cf.cod_barra as Cod_barra,
            sum(est.estoque - est.estoque_retido) as estoque_disponivel
        from
            vw_rs_produto_estoque est (NOLOCK) inner join
            vw_rs_produto vwp (nolock) on vwp.id_produto = est.id_produto inner join
            caixa_fechada cf (nolock) on vwp.id_produto = cf.cod_produto and cf.principal = -1
        where
            vwp.id_fornecedor in ({', '.join(':' + n for n in nomes)}){filtro_filial}
        group by
            vwp.descricao, cf.cod_barra
    """

    try:
        df = _consultar_dataframe(query, params)
        return None if df.empty else df
    except ErroConexaoBanco:
        raise
    except Exception as error:
        logger.error(f"[ERRO NA CONSULTA DE ESTOQUE]: {error}")
        return None
