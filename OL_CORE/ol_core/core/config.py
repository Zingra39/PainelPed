"""Configuração do ol_core — fonte única das variáveis de ambiente.

Regra: o ol_core NÃO carrega `.env` sozinho. Quem carrega é o ponto de
entrada do processo (API ou serviço), uma única vez, chamando
`inicializar_processo(...)` (ou `carregar_ambiente(...)`) antes de usar o
banco/FTP. Depois disso, todo o ol_core lê `os.environ` NA HORA DO USO, por
meio das funções abaixo — nada é congelado em constante de módulo no import.

Ordem de precedência (a primeira que tiver a chave vence):
  1. variáveis já presentes no ambiente do processo (ex.: definidas no
     serviço NSSM, ou herdadas da API quando ela dispara um serviço);
  2. o arquivo apontado por PAINEL_ENV_FILE;
  3. o `.env` padrão do processo (ao lado do main.py / do script / do .exe).

As chaves estão documentadas em `.env.example`, na raiz do projeto.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from ol_core.core.logger import configurar_logs, logger

AMBIENTE_PADRAO = "Homologacao"


# ------------------------------------------------------------------ carga


def carregar_ambiente(arquivo_padrao: Path | str | None = None) -> Path | None:
    """Carrega o `.env` do processo em `os.environ`, sem sobrescrever o que
    já estiver definido. Devolve o arquivo carregado (ou None).

    PAINEL_ENV_FILE, se definida, substitui `arquivo_padrao` — e precisa
    existir: apontar para um arquivo inexistente é erro de implantação, não
    motivo para seguir com a configuração errada.
    """
    explicito = os.getenv("PAINEL_ENV_FILE")
    if explicito:
        caminho = Path(explicito)
        if not caminho.is_file():
            raise RuntimeError(f"PAINEL_ENV_FILE aponta para um arquivo inexistente: {caminho}")
    elif arquivo_padrao:
        caminho = Path(arquivo_padrao)
        if not caminho.is_file():
            return None
    else:
        return None

    load_dotenv(caminho, override=False)
    return caminho


def pasta_da_aplicacao(arquivo_main: str | Path) -> Path:
    """Pasta do ponto de entrada: a do .exe quando empacotado pelo
    PyInstaller, ou a do script (`__file__` de quem chama)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(arquivo_main).resolve().parent


def inicializar_processo(nome: str, pasta: str | Path) -> None:
    """Prepara um processo: carrega `<pasta>/.env` (ou PAINEL_ENV_FILE) e
    configura os logs em LOG_DIR (padrão `<pasta>/logs`), num arquivo
    próprio `<nome>.log`. Chamar uma vez, no início do ponto de entrada."""
    pasta = Path(pasta)
    arquivo = carregar_ambiente(pasta / ".env")
    destino = configurar_logs(nome, pasta / "logs")

    origem = str(arquivo) if arquivo else "somente variáveis do processo"
    logger.info(f"[{nome}] Configuração: {origem} | ambiente={ambiente()} | logs={destino}")
    if not os.getenv("PAINEL_ENV"):
        logger.warning(
            f"PAINEL_ENV não definida — assumindo '{AMBIENTE_PADRAO}' (sem envio ao FTP, "
            "pastas redirecionadas para OL_LOCAL). Em produção, defina PAINEL_ENV=Producao."
        )


# ------------------------------------------------------------------ leitura


def texto(nome: str, padrao: str = "") -> str:
    return os.getenv(nome, padrao)


def inteiro(nome: str, padrao: int) -> int:
    """Lê um inteiro do ambiente; valor ausente ou inválido cai no padrão."""
    bruto = os.getenv(nome)
    try:
        return int(bruto) if bruto not in (None, "") else padrao
    except ValueError:
        logger.warning(f"Variável {nome}='{bruto}' não é um inteiro — usando {padrao}.")
        return padrao


def ambiente() -> str:
    """'Producao' ou 'Homologacao' (padrão). Em homologação não há envio ao FTP."""
    return (os.getenv("PAINEL_ENV") or AMBIENTE_PADRAO).strip().capitalize()


def em_producao() -> bool:
    return ambiente() == "Producao"


def credenciais_ftp() -> tuple[str | None, str | None, str | None]:
    """(servidor, usuário, senha) do FTP — lidos a cada conexão."""
    return os.getenv("FTP_SERVER"), os.getenv("FTP_USER"), os.getenv("FTP_PASSWORD")
