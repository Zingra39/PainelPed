import time

from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.logger import logger
from ol_core.core.conexao import buscar_um


# ------------------------------------------------------------------
# PARAMETRO
# ------------------------------------------------------------------
def obter_valor_parametro(chave: str) -> str | None:
    """Retorna o valor atual de um parâmetro de configuração (tabela
    `parametro`) pela chave.

    Devolve None se o parâmetro não existir ou em caso de erro de banco —
    quem chama deve tratar None como "usar o comportamento padrão", nunca
    como ativação (fail-safe: uma falha de leitura nunca deve ligar um
    comportamento automático por acidente).
    """
    try:
        resultado = buscar_um("SELECT valor FROM parametro WHERE chave = %s", (chave,))
        return resultado["valor"] if resultado else None
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        logger.error(f"[obter_valor_parametro] {erro}")
        return None


def parametro_esta_ativo(chave: str) -> bool:
    """Açúcar sintático sobre obter_valor_parametro para os parâmetros
    booleanos (valor '1' = ligado / '0' ou ausente = desligado).

    Qualquer erro, ausência do parâmetro, ou valor diferente de '1' resulta
    em False — fail-safe.
    """
    return obter_valor_parametro(chave) == "1"


# ------------------------------------------------------------------
# CONFIGURAÇÕES DO DISTRIBUIDOR (tela de Parametrização)
# ------------------------------------------------------------------
CHAVE_CNPJ_DISTRIBUIDOR = "cnpj_distribuidor"
CHAVE_FILIAIS_ESTOQUE = "filiais_estoque"


class ConfiguracaoAusente(ValueError):
    """Configuração obrigatória não preenchida na tela de Parametrização."""


def cnpj_distribuidor() -> str | None:
    """CNPJ do distribuidor (só dígitos), ou None se não configurado."""
    digitos = "".join(c for c in (obter_valor_parametro(CHAVE_CNPJ_DISTRIBUIDOR) or "") if c.isdigit())
    return digitos or None


def exigir_cnpj_distribuidor() -> str:
    """CNPJ do distribuidor para gravar nos arquivos. Sem ele, os arquivos de
    retorno/espelho/cancelamento/estoque sairiam com o campo em branco — então
    a geração é recusada."""
    cnpj = cnpj_distribuidor()
    if not cnpj:
        raise ConfiguracaoAusente(
            "CNPJ do distribuidor não configurado. Informe-o na tela de Parametrização "
            "antes de gerar arquivos."
        )
    return cnpj


def interpretar_filiais(valor: str | None) -> list[int]:
    """'12328, 12329' -> [12328, 12329]. Ignora o que não for número inteiro
    positivo (a API já valida na gravação) e repetições."""
    filiais: list[int] = []
    for parte in (valor or "").replace(";", ",").replace(" ", ",").split(","):
        parte = parte.strip()
        if parte.isdigit() and int(parte) > 0 and int(parte) not in filiais:
            filiais.append(int(parte))
    return filiais


# A validação de pedido consulta estoque item a item; sem cache, cada item
# faria também uma leitura no MySQL. Uma alteração na tela vale em até 1 min.
_CACHE_FILIAIS_SEGUNDOS = 60
_cache_filiais: tuple[float, list[int]] | None = None


def filiais_estoque() -> list[int]:
    """Filiais cujo estoque o sistema considera. Lista vazia = parâmetro não
    configurado: as consultas não filtram por filial (somam todas)."""
    global _cache_filiais
    agora = time.monotonic()
    if _cache_filiais and agora - _cache_filiais[0] < _CACHE_FILIAIS_SEGUNDOS:
        return list(_cache_filiais[1])
    filiais = interpretar_filiais(obter_valor_parametro(CHAVE_FILIAIS_ESTOQUE))
    _cache_filiais = (agora, filiais)
    return list(filiais)
