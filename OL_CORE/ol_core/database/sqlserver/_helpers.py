from ol_core.core.exceptions import ErroConexaoBanco
import pandas as pd
from sqlalchemy import text
from ol_core.core.logger import logger
from ol_core.core.conexao import obter_engine_erp


def _consultar_dataframe(query: str, params=None) -> pd.DataFrame:
    try:
        engine = obter_engine_erp()
        with engine.connect() as conn:
            return pd.read_sql(text(query), conn, params=params or {})
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[consultar_dataframe] {erro}")
        return pd.DataFrame()


def _consultar_linha(query: str, params=None):
    try:
        engine = obter_engine_erp()
        with engine.connect() as conn:
            return conn.execute(text(query), params or {}).fetchone()
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[consultar_linha] {erro}")
        return None
