"""Isolamento do ambiente de homologação.

Quando PAINEL_ENV == "Homologacao", nenhum arquivo de teste pode ir para as pastas
de produção (UNC/rede) cadastradas na tabela `industria`. Este módulo redireciona
todas as pastas da indústria para OL_LOCAL/<industria>/<pasta>, na raiz do projeto.
"""
import os
import re
from pathlib import Path

from ol_core.core.config import ambiente as _ambiente_config  # type: ignore
from ol_core.core.logger import logger  # type: ignore

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
RAIZ_OL_LOCAL = RAIZ_PROJETO / "OL_LOCAL"
_HOSTS_LOCAIS = {"localhost", "127.0.0.1", "::1"}

_PASTAS = (
    "envio", "envio_retorno", "envio_nf", "envio_cancelamento",
    "pedido_original", "entrada", "retorno", "nfe",
    "backup", "cancelamento", "estoque", "erro",
)


def ambiente() -> str:
    # Mesmo critério do envio ao FTP (ol_core.core.config.ambiente).
    return _ambiente_config()


def em_homologacao() -> bool:
    return ambiente() != "Producao"


def esta_em_ol_local(caminho: Path | str | None) -> bool:
    if caminho is None:
        return False
    try:
        Path(caminho).resolve().relative_to(RAIZ_OL_LOCAL.resolve())
        return True
    except ValueError:
        return False


def garantir_ambiente_local() -> None:
    """Trava de segurança da homologação: só segue se o MySQL for local e o ol_core
    em uso for o deste projeto. Deve rodar ANTES de qualquer acesso a banco.

    Sem isso, um venv com `ol_core` instalado de outra cópia do projeto usa o
    código dela e a simulação pode gravar no banco de outro servidor. O .env já
    foi carregado pelo ponto de entrada (inicializar_processo).
    """
    import ol_core  # type: ignore

    host = (os.getenv("MYSQL_HOST") or "").strip().lower()
    if host not in _HOSTS_LOCAIS:
        raise RuntimeError(
            f"Homologação recusada: MYSQL_HOST={host!r} não é local. "
            "A simulação só pode usar o MySQL local."
        )
    origem = Path(ol_core.__file__).resolve()
    try:
        origem.relative_to(RAIZ_PROJETO)
    except ValueError:
        raise RuntimeError(
            f"Homologação recusada: o ol_core em uso ({origem}) não é o deste projeto ({RAIZ_PROJETO})."
        ) from None


def isolar_industria(industria) -> None:
    """Aponta todas as pastas da indústria para OL_LOCAL/<industria>/<pasta> e as cria.

    Falha (RuntimeError) se, depois do redirecionamento, alguma pasta ainda estiver
    fora de OL_LOCAL — nesse caso nada deve ser gerado.
    """
    nome = re.sub(r"[^A-Za-z0-9_-]+", "_", str(industria.nome)).strip("_") or f"industria_{industria.id_industria}"
    base = RAIZ_OL_LOCAL / nome

    for pasta in _PASTAS:
        destino = base / pasta
        destino.mkdir(parents=True, exist_ok=True)
        setattr(industria, f"pasta_{pasta}", destino)

    fora = [p for p in _PASTAS if not esta_em_ol_local(getattr(industria, f"pasta_{p}"))]
    if fora:
        raise RuntimeError(f"Isolamento falhou para '{industria.nome}': pastas fora de OL_LOCAL: {fora}")

    logger.info(f"[homologacao] Pastas de '{industria.nome}' redirecionadas para {base}")
