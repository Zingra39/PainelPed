"""Consulta do título (nota fiscal) do pedido no ERP, para a tela de detalhe."""
import os

import pandas as pd

from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.database.sqlserver.contexto_titulo import verificar_titulo


def _sem_nulo(valor):
    """Converte NaN/NaT (pandas) para None, evitando erro de validação do pydantic."""
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    return valor


def _int_ou_none(valor):
    """Converte para int nativo (o SQL Server/pandas pode retornar numpy.int64), preservando None."""
    valor = _sem_nulo(valor)
    return None if valor is None else int(valor)


def _texto_ou_none(valor):
    """Converte para str nativa — colunas do ERP tipadas como int/numeric (ex.: serie_nf, codigo_situacao)
    quebram a validação do pydantic quando o schema espera Optional[str]."""
    valor = _sem_nulo(valor)
    return None if valor is None else str(valor)


def buscar_titulo_erp(nome_arquivo) -> "dict | None":
    """Busca dados do título no ERP para o arquivo informado. Retorna None se indisponível."""
    if not nome_arquivo:
        return None
    try:
        nome_arquivo_base = os.path.basename(nome_arquivo)
        titulos = verificar_titulo(nome_arquivo_base)
        if not titulos:
            return None
        titulo = next(
            (t for t in titulos if t.nome_arquivo and nome_arquivo_base in os.path.basename(str(t.nome_arquivo))),
            titulos[0],
        )
        return {
            "codigo_titulo": _int_ou_none(getattr(titulo, "codigo_titulo", None)),
            "numero_titulo": _texto_ou_none(getattr(titulo, "numero_titulo", None)),
            "serie_nf": _texto_ou_none(getattr(titulo, "serie_nf", None)),
            "data_emissao": _sem_nulo(getattr(titulo, "data_emissao", None)),
            "data_vencimento": _sem_nulo(getattr(titulo, "data_vencimento", None)),
            "codigo_situacao": _texto_ou_none(getattr(titulo, "codigo_situacao", None)),
            "data_cancelamento": _sem_nulo(getattr(titulo, "data_cancelamento", None)),
            "quem_cancelou": _texto_ou_none(getattr(titulo, "quem_cancelou", None)),
            "chave_acesso": _texto_ou_none(getattr(titulo, "chave_acesso", None)),
        }
    except ErroConexaoBanco:
        raise
    except Exception:
        return None
