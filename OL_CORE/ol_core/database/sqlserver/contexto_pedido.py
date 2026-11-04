from ol_core.core.exceptions import ErroConexaoBanco
import pandas as pd
from ol_core.core.logger import logger
from ol_core.models.pedido import Pedido
from ol_core.models.pedido_item import Pedido_Item
from ol_core.database.sqlserver._helpers import _consultar_dataframe
from ol_core.utils.cnpj import parametros_cnpj


# ------------------------------------------------------------------
# PEDIDO
# ------------------------------------------------------------------
def verifica_arquivos_transmitidos(id_bbs: int, data_alvo: str) -> list[Pedido] | None:
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
            AND p.digitacao >= :data_alvo
    """

    try:
        df = _consultar_dataframe(query, {"id_bbs": id_bbs, "data_alvo": data_alvo})

        if df.empty:
            return None

        df["valor_total"] = pd.to_numeric(df["valor_total"], errors="coerce").fillna(0)

        df["cod_pedido"] = df["cod_pedido"].fillna(0)
        df["numero_pedido"] = df["numero_pedido"].fillna(0)

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


def verifica_itens_pedido_pelo_cod_pedido(codigo_pedido: int) -> list[Pedido_Item] | None:
    try:
        df = _consultar_dataframe(
            """
            select
                p.cod_produto as codigo_produto,
                cf.cod_barra as ean,
                p.separado as quantidade_atendida,
                p.quantidade as quantidade_solicitada,
                p.preco,
                p.pdu as desconto,
                cond.cod_cond as condicao,
                COALESCE(ds.cod_motivo, 0) as cod_motivo
            from
                pedido_item p (NOLOCK)
                LEFT JOIN cond(NOLOCK) ON p.id_cond = cond.id_cond
                LEFT JOIN caixa_fechada cf (NOLOCK) ON cf.cod_produto = p.cod_produto and cf.principal = -1
                LEFT JOIN def_motivo_item ds (NOLOCK) ON ds.cod_motivo = p.motivo
            WHERE p.cod_pedido = :cod_pedido
            """,
            {"cod_pedido": codigo_pedido}
        )

        if df.empty:
            return None

        df["quantidade_atendida"]   = df["quantidade_atendida"].fillna(0)
        df["quantidade_solicitada"] = df["quantidade_solicitada"].fillna(0)
        df["preco"]                 = df["preco"].fillna(0)
        df["desconto"]              = df["desconto"].fillna(0)
        df["condicao"]              = df["condicao"].fillna("")
        df["cod_motivo"]            = df["cod_motivo"].fillna(0)
        df["ean"]                   = df["ean"].fillna("")

        return [
            Pedido_Item(
                codigo_produto=row["codigo_produto"],
                ean=row["ean"],
                quantidade_atendida=row["quantidade_atendida"],
                quantidade_solicitada=row["quantidade_solicitada"],
                preco=round(row["preco"], 2),
                desconto=round(row["desconto"], 2),
                condicao=row["condicao"],
                cod_motivo=row["cod_motivo"],
            )
            for _, row in df.iterrows()
        ]
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verifica_itens_pedido_pelo_cod_pedido] {erro}")


def verifica_itens_pedido_pelo_nome_arquivo(nome_arquivo: str) -> list[Pedido_Item] | None:
    try:
        df = _consultar_dataframe(
            """
            select
                p.cod_produto as codigo_produto,
                cf.cod_barra as ean,
                p.separado as quantidade_atendida,
                p.quantidade as quantidade_solicitada,
                p.preco,
                p.pdu as desconto,
                cond.cod_cond as condicao,
                COALESCE(ds.cod_motivo, 0) as cod_motivo
            from
                pedido_item p (NOLOCK)
                LEFT JOIN log_pedido_webservice lp (NOLOCK) ON lp.cod_pedido = p.cod_pedido
                LEFT JOIN cond(NOLOCK) ON p.id_cond = cond.id_cond
                LEFT JOIN caixa_fechada cf (NOLOCK) ON cf.cod_produto = p.cod_produto and cf.principal = -1
                LEFT JOIN def_motivo_item ds (NOLOCK) ON ds.cod_motivo = p.motivo
            WHERE lp.nome_arquivo = :nome_arquivo
            """,
            {"nome_arquivo": nome_arquivo}
        )

        if df.empty:
            return None

        df["quantidade_atendida"]   = df["quantidade_atendida"].fillna(0)
        df["quantidade_solicitada"] = df["quantidade_solicitada"].fillna(0)
        df["preco"]                 = df["preco"].fillna(0)
        df["desconto"]              = df["desconto"].fillna(0)
        df["condicao"]              = df["condicao"].fillna("")
        df["cod_motivo"]            = df["cod_motivo"].fillna(0)
        df["ean"]                   = df["ean"].fillna("")

        return [
            Pedido_Item(
                codigo_produto=row["codigo_produto"],
                ean=row["ean"],
                quantidade_atendida=row["quantidade_atendida"],
                quantidade_solicitada=row["quantidade_solicitada"],
                preco=round(row["preco"], 2),
                desconto=round(row["desconto"], 2),
                condicao=row["condicao"],
                cod_motivo=row["cod_motivo"],
            )
            for _, row in df.iterrows()
        ]
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verifica_itens_pedido_pelo_cod_pedido] {erro}")


def verificar_primeiro_pedido(cnpj_cliente: str, data: str):
    try:
        df = _consultar_dataframe(
            """
                SELECT Count(*) as pedido_feito
                FROM pedido_oper po (NOLOCK)
                LEFT JOIN pedido p (NOLOCK) ON p.cod_pedido = po.cod_pedido
                LEFT JOIN entidade_doc ed (NOLOCK) ON ed.cod_entidade = po.cod_entidade AND ed.cod_tipo_doc = 3
                WHERE ed.numero IN (:cnpj_cliente, :cnpj_cliente_mascarado)
                AND p.digitacao = :data
            """,
            # Sem dbo.RetiraEspacos_E_CatacteresEspeciais na coluna: a máscara
            # é aplicada no parâmetro (ver ol_core/utils/cnpj.py).
            {**parametros_cnpj(cnpj_cliente, "cnpj_cliente"), "data": data}
        )
        return None if df.empty else df["pedido_feito"].values[0]
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verificar_primeiro_pedido] {erro}")


def verificar_valor_pedido_minimo(condicao: int) -> float:
    try:
        df = _consultar_dataframe(
            """
                SELECT pri_min_valor FROM cond (NOLOCK) WHERE id_cond = :condicao
            """,
            {"condicao": condicao}
        )
        
        if df.empty:
            logger.warning(f"[verificar_valor_pedido_minimo] Nenhum valor mínimo configurado para a condição {condicao}.")
            return 0.0
        
        valor = df["pri_min_valor"].iloc[0]
        
        if pd.isna(valor):
            logger.warning(f"[verificar_valor_pedido_minimo] Valor mínimo configurado como NULL para a condição {condicao}.")
            return 0.0
        
        return round(float(valor), 2)
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verificar_valor_pedido_minimo] {erro}")
        return 0.0


def verifica_pedido(numero_pedido_polo: str) -> list[Pedido] | None:
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
            lp.cod_pedido_polo = :numero_pedido_polo
    """

    try:
        df = _consultar_dataframe(query, {"numero_pedido_polo": numero_pedido_polo})

        if df.empty:
            return None

        df["valor_total"] = pd.to_numeric(df["valor_total"], errors="coerce").fillna(0)

        df["cod_pedido"] = df["cod_pedido"].fillna(0)
        df["numero_pedido"] = df["numero_pedido"].fillna(0)

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
        logger.error(f"[verifica_pedido] {erro}")
        return None


def verifica_todos_itens_pedido_pelo_cod_pedido(codigo_pedido: int) -> list[Pedido_Item] | None:
    try:
        df = _consultar_dataframe(
            """
            select
                p.cod_produto as codigo_produto,
                cf.cod_barra as ean,
                p.separado as quantidade_atendida,
                p.quantidade as quantidade_solicitada,
                p.preco,
                p.pdu as desconto,
                cond.cod_cond as condicao,
                COALESCE(ds.cod_motivo, 0) as cod_motivo
            from
                pedido_item p (NOLOCK)
                LEFT JOIN cond(NOLOCK) ON p.id_cond = cond.id_cond
                LEFT JOIN caixa_fechada cf (NOLOCK) ON cf.cod_produto = p.cod_produto
                LEFT JOIN def_motivo_item ds (NOLOCK) ON ds.cod_motivo = p.motivo
            WHERE p.cod_pedido = :cod_pedido
            """,
            {"cod_pedido": codigo_pedido}
        )

        if df.empty:
            return None

        df["quantidade_atendida"]   = df["quantidade_atendida"].fillna(0)
        df["quantidade_solicitada"] = df["quantidade_solicitada"].fillna(0)
        df["preco"]                 = df["preco"].fillna(0)
        df["desconto"]              = df["desconto"].fillna(0)
        df["condicao"]              = df["condicao"].fillna("")
        df["cod_motivo"]            = df["cod_motivo"].fillna(0)
        df["ean"]                   = df["ean"].fillna("")

        return [
            Pedido_Item(
                codigo_produto=row["codigo_produto"],
                ean=row["ean"],
                quantidade_atendida=row["quantidade_atendida"],
                quantidade_solicitada=row["quantidade_solicitada"],
                preco=round(row["preco"], 2),
                desconto=round(row["desconto"], 2),
                condicao=row["condicao"],
                cod_motivo=row["cod_motivo"],
            )
            for _, row in df.iterrows()
        ]
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verifica_itens_pedido_pelo_cod_pedido] {erro}")


def verifica_todos_eans_itens_pedido_pelo_nome_arquivo(nome_arquivo: str) -> list[Pedido_Item] | None:
    try:
        df = _consultar_dataframe(
            """
            select
                p.cod_produto as codigo_produto,
                cf.cod_barra as ean,
                p.separado as quantidade_atendida,
                p.quantidade as quantidade_solicitada,
                p.preco,
                p.pdu as desconto,
                cond.cod_cond as condicao,
                COALESCE(ds.cod_motivo, 0) as cod_motivo
            from
                pedido_item p (NOLOCK)
                LEFT JOIN log_pedido_webservice lp (NOLOCK) ON lp.cod_pedido = p.cod_pedido
                LEFT JOIN cond(NOLOCK) ON p.id_cond = cond.id_cond
                LEFT JOIN caixa_fechada cf (NOLOCK) ON cf.cod_produto = p.cod_produto
                LEFT JOIN def_motivo_item ds (NOLOCK) ON ds.cod_motivo = p.motivo
            WHERE lp.nome_arquivo = :nome_arquivo
            """,
            {"nome_arquivo": nome_arquivo}
        )

        if df.empty:
            return None

        df["quantidade_atendida"]   = df["quantidade_atendida"].fillna(0)
        df["quantidade_solicitada"] = df["quantidade_solicitada"].fillna(0)
        df["preco"]                 = df["preco"].fillna(0)
        df["desconto"]              = df["desconto"].fillna(0)
        df["condicao"]              = df["condicao"].fillna("")
        df["cod_motivo"]            = df["cod_motivo"].fillna(0)
        df["ean"]                   = df["ean"].fillna("")

        return [
            Pedido_Item(
                codigo_produto=row["codigo_produto"],
                ean=row["ean"],
                quantidade_atendida=row["quantidade_atendida"],
                quantidade_solicitada=row["quantidade_solicitada"],
                preco=round(row["preco"], 2),
                desconto=round(row["desconto"], 2),
                condicao=row["condicao"],
                cod_motivo=row["cod_motivo"],
            )
            for _, row in df.iterrows()
        ]
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[verifica_itens_pedido_pelo_cod_pedido] {erro}")

