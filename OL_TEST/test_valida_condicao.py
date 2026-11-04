"""Testes de ol_core.validators.valida_condicao.valida_condicaos.

A funcao encadeia varias verificacoes sobre a condicao comercial (BBS,
acessivel_outras_cond, condicao mae, cliente na condicao, validade). Aqui a
estrategia e: montar uma condicao "100% valida" como base e, em cada teste,
quebrar so UM campo por vez pra isolar qual verificacao esta sendo testada.
"""
from datetime import datetime, timedelta

from ol_core.validators import valida_condicao
from ol_core.models.enums.tipo_severidade import TipoSeveridade


def _preparar_captura_de_erros(monkeypatch):
    erros_registrados = []
    monkeypatch.setattr(
        valida_condicao, "registrar_ocorrencia",
        lambda erro: erros_registrados.append(erro),
    )
    return erros_registrados


def _condicao_valida(**sobrescreve):
    """Condicao que passa em todas as verificacoes (usada como base)."""
    padrao = dict(
        cod_cond=3692,
        validade_condicao=datetime.now() + timedelta(days=30),
        bbs=-1,
        acessivel_outras_cond=-1,
        acessa_outras_cond=-1,
        todos_clientes=-1,
    )
    padrao.update(sobrescreve)
    return padrao


def test_condicao_nao_cadastrada_registra_erro_e_para_por_ai(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(valida_condicao, "resgatar_condicao", lambda id_cond: None)

    valida_condicao.valida_condicaos(id_cond=3692, cnpj_cliente="12345678000199", numero_pedido_ol="PED001")

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.ERRO.value
    assert "não está cadastrada no Delage" in erros[0].descricao


def test_condicao_sem_data_de_validade_registra_erro_e_nao_continua_as_outras_checagens(monkeypatch):
    # Esse e o cenario do bug corrigido no card #29: antes, quando
    # validade_condicao era None, o codigo tentava chamar .date() nela
    # mesmo assim e estourava AttributeError. Agora ha um "return" logo
    # depois de registrar o erro, entao nenhuma outra checagem roda.
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(
        valida_condicao, "resgatar_condicao",
        lambda id_cond: _condicao_valida(validade_condicao=None, bbs=999),  # bbs invalido de propósito
    )

    valida_condicao.valida_condicaos(id_cond=3692, cnpj_cliente="12345678000199", numero_pedido_ol="PED001")

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.ERRO.value
    assert "não possui data de validade" in erros[0].descricao


def test_condicao_tudo_valido_nao_registra_nenhum_erro(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(valida_condicao, "resgatar_condicao", lambda id_cond: _condicao_valida())

    valida_condicao.valida_condicaos(id_cond=3692, cnpj_cliente="12345678000199", numero_pedido_ol="PED001")

    assert erros == []


def test_condicao_expirada_registra_alerta(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(
        valida_condicao, "resgatar_condicao",
        lambda id_cond: _condicao_valida(validade_condicao=datetime.now() - timedelta(days=1)),
    )

    valida_condicao.valida_condicaos(id_cond=3692, cnpj_cliente="12345678000199", numero_pedido_ol="PED001")

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.ALERTA.value
    assert "expirada" in erros[0].descricao


def test_condicao_sem_flag_bbs_ativa_registra_critico(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(valida_condicao, "resgatar_condicao", lambda id_cond: _condicao_valida(bbs=0))

    valida_condicao.valida_condicaos(id_cond=3692, cnpj_cliente="12345678000199", numero_pedido_ol="PED001")

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.CRITICO.value
    assert "flag BBS" in erros[0].descricao


def test_condicao_sem_flag_acessivel_outras_cond_registra_critico(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(
        valida_condicao, "resgatar_condicao",
        lambda id_cond: _condicao_valida(acessivel_outras_cond=0),
    )

    valida_condicao.valida_condicaos(id_cond=3692, cnpj_cliente="12345678000199", numero_pedido_ol="PED001")

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.CRITICO.value
    assert "acessivel_outras_cond" in erros[0].descricao


def test_condicao_mae_sem_flag_acessa_outras_cond_registra_critico(monkeypatch):
    # A checagem de "acessa_outras_cond" so roda quando id_cond == 3692
    # (a condicao mae).
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(
        valida_condicao, "resgatar_condicao",
        lambda id_cond: _condicao_valida(acessa_outras_cond=0),
    )

    valida_condicao.valida_condicaos(id_cond=3692, cnpj_cliente="12345678000199", numero_pedido_ol="PED001")

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.CRITICO.value
    assert "acessa_outras_cond" in erros[0].descricao


def test_condicao_que_nao_e_mae_ignora_checagem_de_acessa_outras_cond(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(
        valida_condicao, "resgatar_condicao",
        lambda id_cond: _condicao_valida(cod_cond=111, acessa_outras_cond=0),
    )

    # id_cond diferente de 3692 -> checagem de condicao mae nem roda
    valida_condicao.valida_condicaos(id_cond=111, cnpj_cliente="12345678000199", numero_pedido_ol="PED001")

    assert erros == []


def test_condicao_restrita_com_cliente_fora_da_condicao_registra_critico(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(
        valida_condicao, "resgatar_condicao",
        lambda id_cond: _condicao_valida(todos_clientes=0),
    )
    monkeypatch.setattr(valida_condicao, "verifica_cliente_na_condicao", lambda cod_cond, cnpj: False)

    valida_condicao.valida_condicaos(id_cond=3692, cnpj_cliente="99999999000199", numero_pedido_ol="PED001")

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.CRITICO.value
    assert "não está cadastrado na condição" in erros[0].descricao


def test_condicao_restrita_com_cliente_cadastrado_nao_registra_erro(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(
        valida_condicao, "resgatar_condicao",
        lambda id_cond: _condicao_valida(todos_clientes=0),
    )
    monkeypatch.setattr(valida_condicao, "verifica_cliente_na_condicao", lambda cod_cond, cnpj: True)

    valida_condicao.valida_condicaos(id_cond=3692, cnpj_cliente="12345678000199", numero_pedido_ol="PED001")

    assert erros == []
