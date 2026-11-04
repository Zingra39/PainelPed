"""Conftest dos testes de INTEGRAÇÃO real (OL_TEST/integracao/).

Diferença pro resto do OL_TEST: aqui NÃO se usa SQLite nem mocks — os
testes chamam as funções de produção de verdade contra os bancos de
HOMOLOGAÇÃO (MySQL homolog + SQL Server do ERP homolog), usando as
credenciais de `.env.homologacao`.

REGRA DE SEGURANÇA (autorizada explicitamente pelo usuário):
  - Só chamamos funções SOMENTE LEITURA (consultas/SELECT).
  - NUNCA fazemos INSERT, UPDATE, DELETE, CREATE ou ALTER nos bancos de
    homologação, mesmo sendo homolog.
  - As credenciais nunca são impressas/logadas — só o resultado da
    tentativa de conexão (sucesso/falha) é usado, nunca os valores.

Se um dos bancos não estiver alcançável a partir de onde os testes forem
rodados (rede, firewall, VPN etc.), o teste correspondente é pulado
(skip) em vez de falhar — quem rodar esses testes numa máquina com
acesso de verdade aos bancos de homologação (ex.: a própria rede da
empresa) vai vê-los executar de verdade.
"""
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

OL_CORE_PATH = Path(__file__).resolve().parent.parent.parent / "OL_CORE"

# Carrega .env.homologacao do OL_CORE (mesmas chaves MYSQL_*/ERP_* usadas
# em produção) por cima de qualquer .env já carregado — nunca imprime os
# valores.
_ENV_HOMOLOG = OL_CORE_PATH / "ol_core" / ".env.homologacao"
if _ENV_HOMOLOG.exists():
    load_dotenv(dotenv_path=_ENV_HOMOLOG, override=True)


@pytest.fixture(scope="session")
def mysql_homolog_disponivel():
    """Tenta abrir e fechar uma conexão real com o MySQL de homologação.
    Pula os testes que dependem disso se não conseguir (ambiente sem
    rede até o host, credenciais ausentes, etc.) — nunca falha o teste
    nem imprime a credencial usada."""
    from ol_core.core.conexao import obter_conexao_mysql

    try:
        conn = obter_conexao_mysql()
        conn.close()
    except Exception as erro:
        pytest.skip(
            f"MySQL de homologação inalcançável a partir deste ambiente "
            f"({type(erro).__name__}). Rode esta suíte numa máquina com "
            f"acesso de rede ao host de homologação."
        )


@pytest.fixture(scope="session")
def sqlserver_homolog_disponivel():
    """Idem, para o SQL Server do ERP (via pyodbc, o mesmo driver usado
    em produção por `obter_engine_erp`). Pula se faltar o driver ODBC do
    sistema (libodbc) OU se o servidor estiver inalcançável."""
    try:
        import pyodbc  # noqa: F401
    except ImportError as erro:
        pytest.skip(
            f"Driver pyodbc/ODBC do sistema indisponível neste ambiente "
            f"({erro}). Rode esta suíte numa máquina com o driver "
            f"'ODBC Driver 18 for SQL Server' instalado."
        )
        return

    servidor = os.getenv("ERP_SERVIDOR")
    banco = os.getenv("ERP_BANCO")
    usuario = os.getenv("ERP_USUARIO")
    senha = os.getenv("ERP_SENHA")

    try:
        conn = pyodbc.connect(
            "DRIVER=ODBC Driver 18 for SQL Server;"
            f"SERVER={servidor};DATABASE={banco};UID={usuario};PWD={senha};"
            "TrustServerCertificate=yes;",
            timeout=5,
        )
        conn.close()
    except Exception as erro:
        pytest.skip(
            f"SQL Server do ERP (homolog) inalcançável a partir deste "
            f"ambiente ({type(erro).__name__}). Rode esta suíte numa "
            f"máquina com acesso de rede ao ERP."
        )
