"""Testes de ol_core.database.mysql.contexto_parametros — leitura da tabela
`parametro` usada pela tela de parametrização (Card de transmissão
automática, squad review 2026-09-17).

Segue a convenção do resto do OL_TEST (ver conftest.py): monkeypatch aponta
pro nome como foi importado dentro do módulo testado
(contexto_parametros.buscar_um), nunca pro módulo original
(ol_core.core.conexao.buscar_um). Nenhum teste aqui toca o MySQL de verdade.
"""
from ol_core.database.mysql import contexto_parametros


# --------------------------------------------------------------------- obter_valor_parametro

def test_obter_valor_parametro_retorna_o_valor_quando_encontrado(monkeypatch):
    monkeypatch.setattr(contexto_parametros, "buscar_um", lambda sql, args=None: {"valor": "1"})

    assert contexto_parametros.obter_valor_parametro("transmissao_automatica_pronto") == "1"


def test_obter_valor_parametro_retorna_none_quando_a_chave_nao_existe(monkeypatch):
    monkeypatch.setattr(contexto_parametros, "buscar_um", lambda sql, args=None: None)

    assert contexto_parametros.obter_valor_parametro("chave_inexistente") is None


def test_obter_valor_parametro_retorna_none_em_caso_de_erro_de_banco(monkeypatch):
    def _levanta(sql, args=None):
        raise RuntimeError("falha simulada de conexão")

    monkeypatch.setattr(contexto_parametros, "buscar_um", _levanta)

    # Fail-safe: erro de banco nunca deve virar exceção pra quem chama, nem
    # travar o fluxo de importação de pedidos por causa de uma leitura de
    # parâmetro que falhou.
    assert contexto_parametros.obter_valor_parametro("qualquer_chave") is None


# --------------------------------------------------------------------- parametro_esta_ativo

def test_parametro_esta_ativo_retorna_true_somente_quando_valor_e_1(monkeypatch):
    monkeypatch.setattr(contexto_parametros, "buscar_um", lambda sql, args=None: {"valor": "1"})

    assert contexto_parametros.parametro_esta_ativo("transmissao_automatica_pronto") is True


def test_parametro_esta_ativo_retorna_false_para_0(monkeypatch):
    monkeypatch.setattr(contexto_parametros, "buscar_um", lambda sql, args=None: {"valor": "0"})

    assert contexto_parametros.parametro_esta_ativo("transmissao_automatica_pronto") is False


def test_parametro_esta_ativo_retorna_false_quando_o_parametro_nao_existe(monkeypatch):
    monkeypatch.setattr(contexto_parametros, "buscar_um", lambda sql, args=None: None)

    # Fail-safe: parâmetro não cadastrado nunca liga o comportamento
    # automático por acidente.
    assert contexto_parametros.parametro_esta_ativo("chave_inexistente") is False


def test_parametro_esta_ativo_retorna_false_em_caso_de_erro_de_banco(monkeypatch):
    def _levanta(sql, args=None):
        raise RuntimeError("falha simulada de conexão")

    monkeypatch.setattr(contexto_parametros, "buscar_um", _levanta)

    assert contexto_parametros.parametro_esta_ativo("transmissao_automatica_pronto") is False
