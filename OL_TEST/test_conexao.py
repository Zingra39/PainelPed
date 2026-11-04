"""Testes de ol_core.core.conexao: transação única, tradução de erro de
conexão, retry na abertura e timeouts vindos do .env. Sem banco de verdade."""
import pymysql
import pytest

from ol_core.core import conexao
from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.utils.cnpj import formatar_cnpj, parametros_cnpj, somente_digitos


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.lastrowid = 10
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, args=None):
        if self.conn.erro:
            raise self.conn.erro
        self.conn.comandos.append(sql)

    def executemany(self, sql, lista):
        self.conn.comandos.append(sql)

    def fetchone(self):
        return {"ok": 1}

    def fetchall(self):
        return [{"ok": 1}]


class _Conexao:
    def __init__(self, erro=None):
        self.erro = erro
        self.comandos: list[str] = []
        self.commits = self.rollbacks = self.fechada = 0

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.fechada += 1


@pytest.fixture
def conexoes(monkeypatch):
    abertas: list[_Conexao] = []

    def abrir():
        c = _Conexao()
        abertas.append(c)
        return c

    monkeypatch.setattr(conexao, "obter_conexao_mysql", abrir)
    return abertas


# ----------------------------------------------------------------- transação (item 2)

def test_sem_transacao_cada_comando_abre_e_commita_a_propria_conexao(conexoes):
    conexao.executar("UPDATE a")
    conexao.inserir("INSERT b")
    assert len(conexoes) == 2
    assert [c.commits for c in conexoes] == [1, 1]


def test_dentro_da_transacao_todos_os_comandos_usam_uma_conexao_e_um_commit(conexoes):
    with conexao.transacao():
        conexao.inserir("INSERT pedido")
        conexao.executar_varios("INSERT item", [(1,), (2,)])
        conexao.executar("UPDATE arquivo")
        conexao.buscar_um("SELECT 1")

    (unica,) = conexoes
    assert unica.comandos == ["INSERT pedido", "INSERT item", "UPDATE arquivo", "SELECT 1"]
    assert unica.commits == 1
    assert unica.rollbacks == 0
    assert unica.fechada == 1


def test_excecao_dentro_da_transacao_faz_rollback_e_nao_commita(conexoes):
    with pytest.raises(ValueError):
        with conexao.transacao():
            conexao.inserir("INSERT pedido")
            raise ValueError("itens falharam")

    (unica,) = conexoes
    assert unica.commits == 0
    assert unica.rollbacks == 1
    assert unica.fechada == 1


def test_transacao_aninhada_reaproveita_a_de_fora(conexoes):
    with conexao.transacao():
        with conexao.transacao():
            conexao.executar("UPDATE a")
        conexao.executar("UPDATE b")
    (unica,) = conexoes
    assert unica.commits == 1


def test_depois_da_transacao_volta_a_abrir_conexao_propria(conexoes):
    with conexao.transacao():
        conexao.executar("UPDATE a")
    conexao.executar("UPDATE b")
    assert len(conexoes) == 2


# ----------------------------------------------------------------- erro de conexão (itens 1/4, A1)

@pytest.mark.parametrize("codigo", [2003, 2006, 2013, 2055, 1045])
def test_erro_de_conexao_do_mysql_vira_erro_conexao_banco(monkeypatch, codigo):
    conn = _Conexao(erro=pymysql.err.OperationalError(codigo, "falhou"))
    monkeypatch.setattr(conexao, "obter_conexao_mysql", lambda: conn)

    with pytest.raises(ErroConexaoBanco) as exc:
        conexao.buscar_todos("SELECT 1")
    assert "Houve um problema de conexão com o banco de dados" in exc.value.detail
    assert exc.value.status_code == 503


def test_erro_de_sql_comum_nao_vira_erro_de_conexao(monkeypatch):
    conn = _Conexao(erro=pymysql.err.ProgrammingError(1064, "syntax error"))
    monkeypatch.setattr(conexao, "obter_conexao_mysql", lambda: conn)

    with pytest.raises(pymysql.err.ProgrammingError):
        conexao.buscar_todos("SELEC 1")


def test_abertura_usa_timeouts_do_env_e_tenta_de_novo(monkeypatch):
    for chave, valor in {
        "MYSQL_HOST": "h", "MYSQL_USUARIO": "u", "MYSQL_SENHA": "s", "MYSQL_BANCO": "b",
        "MYSQL_CONNECT_TIMEOUT": "3", "MYSQL_READ_TIMEOUT": "7", "MYSQL_WRITE_TIMEOUT": "9",
        "MYSQL_CONEXAO_TENTATIVAS": "2",
    }.items():
        monkeypatch.setenv(chave, valor)
    monkeypatch.setattr(conexao.time, "sleep", lambda s: None)

    chamadas = []

    def connect(**kwargs):
        chamadas.append(kwargs)
        if len(chamadas) == 1:
            raise pymysql.err.OperationalError(2003, "Can't connect")
        return "conexao"

    monkeypatch.setattr(conexao.pymysql, "connect", connect)

    assert conexao.obter_conexao_mysql() == "conexao"
    assert len(chamadas) == 2
    assert (chamadas[0]["connect_timeout"], chamadas[0]["read_timeout"], chamadas[0]["write_timeout"]) == (3, 7, 9)


def test_abertura_esgota_tentativas_e_levanta_erro_conexao_banco(monkeypatch):
    for chave, valor in {"MYSQL_HOST": "h", "MYSQL_USUARIO": "u", "MYSQL_SENHA": "s",
                         "MYSQL_BANCO": "b", "MYSQL_CONEXAO_TENTATIVAS": "3"}.items():
        monkeypatch.setenv(chave, valor)
    monkeypatch.setattr(conexao.time, "sleep", lambda s: None)
    tentativas = []

    def connect(**kwargs):
        tentativas.append(1)
        raise pymysql.err.OperationalError(2003, "Can't connect")

    monkeypatch.setattr(conexao.pymysql, "connect", connect)

    with pytest.raises(ErroConexaoBanco):
        conexao.obter_conexao_mysql()
    assert len(tentativas) == 3


@pytest.mark.parametrize("sqlstate, esperado", [("08001", True), ("08S01", True), ("HYT00", True), ("42S02", False)])
def test_classificacao_de_erro_do_erp(sqlstate, esperado):
    assert conexao.eh_erro_conexao_erp(Exception(sqlstate, "msg")) is esperado


# ----------------------------------------------------------------- CNPJ (item 5)

def test_cnpj_formatado_e_sem_mascara():
    assert somente_digitos("43.410.436/0001-61") == "43410436000161"
    assert formatar_cnpj("43410436000161") == "43.410.436/0001-61"
    assert formatar_cnpj(" 43.410.436/0001-61 ") == "43.410.436/0001-61"
    assert formatar_cnpj("123") == "123"
    assert parametros_cnpj("43410436000161", "cnpj_cliente") == {
        "cnpj_cliente": "43410436000161",
        "cnpj_cliente_mascarado": "43.410.436/0001-61",
    }
