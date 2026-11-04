import os
import time
import urllib.parse
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Iterator

import pymysql
import pymysql.cursors
from sqlalchemy import create_engine, event, Engine

from ol_core.core.config import inteiro as _env_int
from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.logger import logger

# Credenciais e timeouts são lidos de os.environ a cada conexão — quem carrega
# o .env é o ponto de entrada do processo (ver ol_core/core/config.py).


# ------------------------------------------------------------------
# Timeouts (segundos) — todos configuráveis no ambiente (ver .env.example).
#
#   MYSQL_CONNECT_TIMEOUT   abrir a conexão com o MySQL
#   MYSQL_READ_TIMEOUT      esperar a resposta de um comando no MySQL
#   MYSQL_WRITE_TIMEOUT     enviar um comando ao MySQL
#   MYSQL_CONEXAO_TENTATIVAS  tentativas de ABRIR a conexão (1 = sem retry)
#   ERP_CONNECT_TIMEOUT     login no SQL Server do ERP
#   ERP_QUERY_TIMEOUT       duração máxima de uma consulta no ERP
#   ERP_POOL_TIMEOUT        espera por uma conexão livre no pool do ERP
#
# Sem timeout, um servidor que não responde deixa a chamada pendurada por
# minutos (o padrão do driver) e trava o serviço/a requisição junto.
# ------------------------------------------------------------------
def _timeouts_mysql() -> dict:
    return {
        "connect_timeout": _env_int("MYSQL_CONNECT_TIMEOUT", 5),
        "read_timeout": _env_int("MYSQL_READ_TIMEOUT", 30),
        "write_timeout": _env_int("MYSQL_WRITE_TIMEOUT", 30),
    }


# ------------------------------------------------------------------
# Tradução de erro de conexão
# ------------------------------------------------------------------
# Códigos do cliente/servidor MySQL que significam "não há conexão utilizável"
# (e não "o SQL está errado"): 1040 too many connections, 1045 acesso negado,
# 2002/2003 servidor inacessível, 2005 host desconhecido, 2006 server has gone
# away, 2013 conexão perdida durante a consulta (inclui read_timeout estourado),
# 2055 conexão perdida no handshake.
_CODIGOS_CONEXAO_MYSQL = {1040, 1045, 2002, 2003, 2005, 2006, 2013, 2055}

# SQLSTATEs do ODBC/pyodbc para falha de conexão ou timeout.
_SQLSTATES_CONEXAO_ERP = {"08001", "08003", "08004", "08S01", "HYT00", "HYT01"}


def eh_erro_conexao_mysql(erro: BaseException) -> bool:
    if isinstance(erro, pymysql.err.InterfaceError):
        return True  # conexão já fechada/inutilizável
    if isinstance(erro, pymysql.err.OperationalError):
        codigo = erro.args[0] if erro.args else None
        return codigo in _CODIGOS_CONEXAO_MYSQL
    return isinstance(erro, (TimeoutError, ConnectionError))


def eh_erro_conexao_erp(erro: BaseException) -> bool:
    sqlstate = erro.args[0] if getattr(erro, "args", None) else None
    return (isinstance(sqlstate, str) and sqlstate.upper() in _SQLSTATES_CONEXAO_ERP) or isinstance(
        erro, (TimeoutError, ConnectionError)
    )


@contextmanager
def _traduzindo_erro_mysql() -> Iterator[None]:
    """Converte erro de conexão do pymysql em ErroConexaoBanco. Qualquer outro
    erro (SQL inválido, constraint…) passa intacto."""
    try:
        yield
    except ErroConexaoBanco:
        raise
    except Exception as erro:
        if eh_erro_conexao_mysql(erro):
            raise ErroConexaoBanco("MySQL", str(erro)) from erro
        raise


def traduzir_erros_de_conexao(engine: Engine, banco: str, eh_erro_conexao: Callable[[BaseException], bool]) -> None:
    """Faz uma engine SQLAlchemy levantar ErroConexaoBanco em vez do
    OperationalError cru quando o problema é de conexão — vale para a abertura
    da conexão e para quedas no meio de uma consulta. Usada pela engine do ERP
    (aqui) e pela engine do MySQL da API (OL_API/app/core/database.py)."""

    @event.listens_for(engine, "handle_error")
    def _ao_errar(contexto):  # noqa: ANN001 — assinatura do evento
        original = contexto.original_exception
        if contexto.is_disconnect or eh_erro_conexao(original):
            raise ErroConexaoBanco(banco, str(original)) from original


# ------------------------------------------------------------------
# SQL Server — ERP(somente consulta)
# ------------------------------------------------------------------
_engine_erp: Engine | None = None


def obter_engine_erp() -> Engine:
    """
    Retorna a engine de conexão com o SQL Server do ERP.
    A engine é criada uma única vez e reutilizada em todas as chamadas,
    evitando abertura excessiva de conexões.

    Raises:
        RuntimeError: Se as variáveis de ambiente não estiverem configuradas.
    """
    global _engine_erp

    if _engine_erp is not None:
        return _engine_erp

    servidor   = os.getenv("ERP_SERVIDOR")
    banco      = os.getenv("ERP_BANCO")
    usuario    = os.getenv("ERP_USUARIO")
    senha      = os.getenv("ERP_SENHA")

    if not all([servidor, banco, usuario, senha]):
        raise RuntimeError(
            "Variáveis de ambiente do SQL Server não configuradas. "
            "Verifique: ERP_SERVIDOR, ERP_BANCO, ERP_USUARIO, ERP_SENHA"
        )

    odbc_str = (
        "DRIVER=ODBC Driver 18 for SQL Server;"
        f"SERVER={servidor};"
        f"DATABASE={banco};"
        f"UID={usuario};"
        f"PWD={senha};"
        "TrustServerCertificate=yes;"
    )

    conn_str = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(odbc_str)}"

    query_timeout = _env_int("ERP_QUERY_TIMEOUT", 60)

    engine = create_engine(
        conn_str,
        fast_executemany=True,
        pool_pre_ping=True,
        pool_timeout=_env_int("ERP_POOL_TIMEOUT", 10),
        # `timeout` do pyodbc.connect = timeout de LOGIN no servidor.
        connect_args={"timeout": _env_int("ERP_CONNECT_TIMEOUT", 10)},
    )

    @event.listens_for(engine, "connect")
    def _definir_timeout_consulta(dbapi_conn, _registro):  # noqa: ANN001
        # Connection.timeout do pyodbc = tempo máximo de cada consulta; ao
        # estourar, o driver cancela e levanta HYT00 (vira ErroConexaoBanco).
        dbapi_conn.timeout = query_timeout

    traduzir_erros_de_conexao(engine, "ERP", eh_erro_conexao_erp)
    _engine_erp = engine
    return _engine_erp


# ------------------------------------------------------------------
# MySQL — Banco operacional do sistema
# ------------------------------------------------------------------
def obter_conexao_mysql() -> pymysql.connections.Connection:
    """
    Abre e retorna uma nova conexão com o banco MySQL operacional, com os
    timeouts do .env. Falha de conexão vira ErroConexaoBanco.

    A ABERTURA é repetida até MYSQL_CONEXAO_TENTATIVAS vezes: nada foi enviado
    ao banco ainda, então repetir é seguro mesmo para escrita. Comandos já
    enviados nunca são repetidos (exigiriam idempotência).

    Prefira executar/inserir/buscar_* ou `transacao()` a usar esta função
    diretamente.

    Raises:
        RuntimeError: Se as variáveis de ambiente não estiverem configuradas.
        ErroConexaoBanco: Se não for possível conectar.
    """
    host     = os.getenv("MYSQL_HOST")
    usuario  = os.getenv("MYSQL_USUARIO")
    senha    = os.getenv("MYSQL_SENHA")
    banco    = os.getenv("MYSQL_BANCO")

    if not all([host, usuario, senha, banco]):
        raise RuntimeError(
            "Variáveis de ambiente do MySQL não configuradas. "
            "Verifique: MYSQL_HOST, MYSQL_USUARIO, MYSQL_SENHA, MYSQL_BANCO"
        )

    tentativas = max(1, _env_int("MYSQL_CONEXAO_TENTATIVAS", 2))
    for tentativa in range(1, tentativas + 1):
        try:
            with _traduzindo_erro_mysql():
                return pymysql.connect(
                    host=host,
                    port=_env_int("MYSQL_PORTA", 3306),
                    user=usuario,
                    password=senha,
                    database=banco,
                    charset="utf8mb4",
                    cursorclass=pymysql.cursors.DictCursor,
                    autocommit=False,
                    **_timeouts_mysql(),
                )
        except ErroConexaoBanco as erro:
            if tentativa == tentativas:
                raise
            logger.warning(f"Falha ao conectar no MySQL (tentativa {tentativa}/{tentativas}): {erro.causa}")
            time.sleep(1)
    raise AssertionError("inalcançável")


# Conexão da transação em andamento (ver `transacao`). ContextVar e não
# global: cada thread/requisição da API enxerga só a sua.
_conexao_da_transacao: ContextVar[pymysql.connections.Connection | None] = ContextVar(
    "_conexao_da_transacao", default=None
)


@contextmanager
def transacao() -> Iterator[pymysql.connections.Connection]:
    """Agrupa vários comandos numa única conexão e num único COMMIT.

        with transacao():
            inserir_pedido(...)
            inserir_pedido_itens(...)
            registrar_arquivo(...)

    Toda chamada a executar/inserir/executar_varios/buscar_* feita dentro do
    bloco — inclusive nas funções de contexto, que não precisam saber disso —
    usa a mesma conexão. Se o bloco levantar exceção, nada é gravado
    (ROLLBACK). Transações aninhadas reaproveitam a de fora.

    Atenção: as funções de contexto engolem erros de SQL e devolvem None; quem
    usa `transacao()` precisa conferir o retorno e LEVANTAR para desfazer.
    """
    atual = _conexao_da_transacao.get()
    if atual is not None:
        yield atual
        return

    conn = obter_conexao_mysql()
    token = _conexao_da_transacao.set(conn)
    try:
        yield conn
        with _traduzindo_erro_mysql():
            conn.commit()
    except BaseException:
        try:
            conn.rollback()
        except Exception as erro_rollback:  # conexão já caiu: o servidor descarta sozinho
            logger.warning(f"Rollback não executado: {erro_rollback}")
        raise
    finally:
        _conexao_da_transacao.reset(token)
        try:
            conn.close()
        except Exception:
            pass


@contextmanager
def _conexao() -> Iterator[pymysql.connections.Connection]:
    """Conexão para um comando avulso: a da transação em andamento, se houver
    (sem commit — quem commita é `transacao`), ou uma nova, commitada e
    fechada ao fim."""
    atual = _conexao_da_transacao.get()
    if atual is not None:
        with _traduzindo_erro_mysql():
            yield atual
        return

    conn = obter_conexao_mysql()
    try:
        with _traduzindo_erro_mysql():
            yield conn
            conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def executar(sql: str, args=None) -> None:
    with _conexao() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, args)


def executar_contando(sql: str, args=None) -> int:
    """Como `executar`, mas devolve quantas linhas o comando alterou — base dos
    UPDATEs condicionais (compare-and-set), em que 0 significa "a condição já
    não valia, nada foi gravado"."""
    with _conexao() as conn:
        with conn.cursor() as cursor:
            return int(cursor.execute(sql, args) or 0)


def executar_varios(sql: str, lista_args) -> int:
    """executemany numa só ida ao banco; devolve as linhas afetadas."""
    with _conexao() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(sql, lista_args)
            return int(cursor.rowcount or 0)


def inserir(sql: str, args=None) -> int | None:
    with _conexao() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, args)
            return cursor.lastrowid


def buscar_um(sql: str, args=None) -> dict | None:
    with _conexao() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, args)
            return cursor.fetchone()


def buscar_todos(sql: str, args=None) -> list[dict]:
    with _conexao() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, args)
            return cursor.fetchall()
