"""Logger do PainelPed.

Importar `logger` não cria arquivo nem handler: quem configura é o ponto de
entrada do processo, via `configurar_logs(...)` (normalmente por meio de
`ol_core.core.config.inicializar_processo`). Antes disso — e em testes —
avisos e erros caem no handler padrão do Python (stderr) e nada vai para disco.

Cada processo grava no PRÓPRIO arquivo (`<LOG_DIR>/<processo>.log`), com
rotação por tamanho: arquivos de log compartilhados entre processos não
rotacionam com segurança no Windows.

Para identificar o pedido em cada linha, envolva o processamento em
`with contexto_pedido(numero_pedido_ol): ...` — o número aparece entre
colchetes no início da mensagem.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterator

NOME_LOGGER = "PainelPed"

_pedido_atual: ContextVar[str | None] = ContextVar("_pedido_atual", default=None)


class _FiltroPedido(logging.Filter):
    """Preenche %(pedido)s com o número do pedido em processamento."""

    def filter(self, record: logging.LogRecord) -> bool:
        numero = _pedido_atual.get()
        record.pedido = f"[{numero}] " if numero else ""
        return True


@contextmanager
def contexto_pedido(numero_pedido_ol: str | None) -> Iterator[None]:
    """Marca as linhas de log emitidas dentro do bloco com o número do pedido.
    Vale por thread/requisição (ContextVar); blocos aninhados usam o mais interno."""
    token = _pedido_atual.set(str(numero_pedido_ol) if numero_pedido_ol else None)
    try:
        yield
    finally:
        _pedido_atual.reset(token)


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome) or padrao)
    except ValueError:
        return padrao


def configurar_logs(processo: str, pasta_padrao: str | Path | None = None, nivel: int = logging.INFO) -> Path | None:
    """Liga console + arquivo rotativo `<LOG_DIR>/<processo>.log`.

    LOG_DIR (variável de ambiente) tem prioridade sobre `pasta_padrao`; sem
    nenhum dos dois, só o console. Rotação: LOG_MAX_MB (padrão 10) por
    arquivo, LOG_BACKUPS (padrão 10) arquivos antigos. Pode ser chamada de
    novo: substitui os handlers da chamada anterior. Devolve o arquivo de log.
    """
    for handler in [h for h in logger.handlers if getattr(h, "_painelped", False)]:
        logger.removeHandler(handler)
        handler.close()

    logger.setLevel(nivel)
    filtro = _FiltroPedido()

    console = logging.StreamHandler()
    console.setLevel(nivel)
    console.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(pedido)s%(message)s", datefmt="%H:%M:%S"))
    handlers: list[logging.Handler] = [console]

    pasta = os.getenv("LOG_DIR") or pasta_padrao
    arquivo: Path | None = None
    if pasta:
        arquivo = Path(pasta) / f"{processo}.log"
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        em_arquivo = RotatingFileHandler(
            arquivo,
            maxBytes=_env_int("LOG_MAX_MB", 10) * 1024 * 1024,
            backupCount=_env_int("LOG_BACKUPS", 10),
            encoding="utf-8",
            delay=True,
        )
        em_arquivo.setLevel(logging.DEBUG)
        em_arquivo.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(process)d | %(module)s | %(pedido)s%(message)s"
        ))
        handlers.append(em_arquivo)

    for handler in handlers:
        handler.addFilter(filtro)
        handler._painelped = True  # type: ignore[attr-defined]
        logger.addHandler(handler)

    # Já tem saída própria: não duplica no root (ex.: o do uvicorn).
    logger.propagate = False
    return arquivo


logger = logging.getLogger(NOME_LOGGER)
logger.setLevel(logging.INFO)
