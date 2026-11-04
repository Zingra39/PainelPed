"""Testes de contexto_pedidos.atualizar_quantidade_atendida_itens.

A conexão MySQL é substituída por um fake: nenhum teste toca o banco de verdade.
"""
import pymysql
import pytest

from ol_core.core import conexao as conexao_mod
from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.database.mysql import contexto_pedidos


class _CursorFalso:
    def __init__(self, rowcount):
        self.rowcount = rowcount
        self.chamadas = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def executemany(self, sql, parametros):
        self.chamadas.append((sql, list(parametros)))


class _ConexaoFalsa:
    def __init__(self, rowcount=0):
        self.cursor_falso = _CursorFalso(rowcount)
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return self.cursor_falso

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


# A conexão agora é aberta pelos helpers de ol_core.core.conexao (executar_varios),
# que participam de `transacao()` quando há uma em andamento.

def test_atualiza_por_numero_pedido_e_ean_numa_unica_transacao(monkeypatch):
    conexao = _ConexaoFalsa(rowcount=2)
    monkeypatch.setattr(conexao_mod, "obter_conexao_mysql", lambda: conexao)

    alteradas = contexto_pedidos.atualizar_quantidade_atendida_itens(
        "PED1", {"7890000000001": 7, "7890000000002": 3}
    )

    assert alteradas == 2
    assert conexao.commits == 1
    (sql, parametros), = conexao.cursor_falso.chamadas
    assert "UPDATE pedido_item SET quantidade_atendida" in sql
    assert "numero_pedido_ol = %s AND ean = %s" in sql
    assert parametros == [(7, "PED1", "7890000000001"), (3, "PED1", "7890000000002")]


@pytest.mark.parametrize("numero, quantidades", [("", {"1": 1}), ("PED1", {}), (None, {"1": 1})])
def test_sem_pedido_ou_sem_quantidades_nao_abre_conexao(monkeypatch, numero, quantidades):
    def nao_deveria_conectar():
        raise AssertionError("não deveria abrir conexão")

    monkeypatch.setattr(conexao_mod, "obter_conexao_mysql", nao_deveria_conectar)

    assert contexto_pedidos.atualizar_quantidade_atendida_itens(numero, quantidades) == 0


def test_erro_de_sql_e_logado_e_devolve_zero_sem_propagar(monkeypatch):
    def conexao_com_erro():
        raise RuntimeError("erro qualquer que não é de conexão")

    monkeypatch.setattr(conexao_mod, "obter_conexao_mysql", conexao_com_erro)

    assert contexto_pedidos.atualizar_quantidade_atendida_itens("PED1", {"7890000000001": 7}) == 0


def test_queda_do_banco_no_meio_do_executemany_propaga_em_vez_de_virar_zero(monkeypatch):
    # Achado A1 da auditoria: uma queda (2013) no meio do executemany saía como
    # erro cru e o `except Exception` devolvia 0 — banco fora tratado como
    # "nenhuma linha". Agora vira ErroConexaoBanco e sobe.
    conexao = _ConexaoFalsa()

    def executemany_cai(sql, parametros):
        raise pymysql.err.OperationalError(2013, "Lost connection to MySQL server during query")

    conexao.cursor_falso.executemany = executemany_cai
    monkeypatch.setattr(conexao_mod, "obter_conexao_mysql", lambda: conexao)

    with pytest.raises(ErroConexaoBanco):
        contexto_pedidos.atualizar_quantidade_atendida_itens("PED1", {"7890000000001": 7})
