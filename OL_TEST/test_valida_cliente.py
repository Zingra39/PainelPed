"""Testes de ol_core.validators.valida_cliente.valida_clientes.

A funcao nao retorna nada: ela so registra ocorrencias (via
registrar_ocorrencia) quando encontra algum problema no cliente. Por isso os
testes capturam os Erro(...) passados pra registrar_ocorrencia numa lista e
conferem o conteudo dessa lista.
"""
from datetime import datetime, timedelta

from ol_core.validators import valida_cliente
from ol_core.models.enums.tipo_severidade import TipoSeveridade
from .conftest import criar_pedido


def _preparar_captura_de_erros(monkeypatch):
    """Troca registrar_ocorrencia por uma funcao que so guarda os erros
    numa lista, em vez de gravar no banco de verdade."""
    erros_registrados = []
    monkeypatch.setattr(
        valida_cliente, "registrar_ocorrencia",
        lambda erro: erros_registrados.append(erro),
    )
    return erros_registrados


def test_cliente_nao_cadastrado_registra_erro(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(valida_cliente, "resgatar_cliente", lambda cnpj: None)

    pedido = criar_pedido(cnpj_cliente="12345678000199")
    valida_cliente.valida_clientes(pedido)

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.ERRO.value
    assert "não está cadastrado" in erros[0].descricao


def test_cliente_bloqueado_registra_alerta(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(
        valida_cliente, "resgatar_cliente",
        lambda cnpj: {
            "situacao_entidade": "Bloqueado",
            "razao_social": "Cliente Teste LTDA",
            "cnpj": cnpj,
            "vencimento_alvara": None,
        },
    )

    pedido = criar_pedido()
    valida_cliente.valida_clientes(pedido)

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.ALERTA.value
    assert "bloqueado" in erros[0].descricao


def test_cliente_inativo_registra_alerta(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(
        valida_cliente, "resgatar_cliente",
        lambda cnpj: {
            "situacao_entidade": " Inativo ",  # com espaços, igual pode vir do banco
            "razao_social": "Cliente Teste LTDA",
            "cnpj": cnpj,
            "vencimento_alvara": None,
        },
    )

    pedido = criar_pedido()
    valida_cliente.valida_clientes(pedido)

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.ALERTA.value


def test_cliente_com_alvara_vencido_registra_alerta(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(
        valida_cliente, "resgatar_cliente",
        lambda cnpj: {
            "situacao_entidade": "Ativo",
            "razao_social": "Cliente Teste LTDA",
            "cnpj": cnpj,
            "vencimento_alvara": datetime.now() - timedelta(days=1),
        },
    )

    pedido = criar_pedido()
    valida_cliente.valida_clientes(pedido)

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.ALERTA.value
    assert "alvara vencido" in erros[0].descricao


def test_cliente_ativo_com_alvara_valido_nao_registra_nenhum_erro(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(
        valida_cliente, "resgatar_cliente",
        lambda cnpj: {
            "situacao_entidade": "Ativo",
            "razao_social": "Cliente Teste LTDA",
            "cnpj": cnpj,
            "vencimento_alvara": datetime.now() + timedelta(days=30),
        },
    )

    pedido = criar_pedido()
    valida_cliente.valida_clientes(pedido)

    assert erros == []


def test_cliente_ativo_sem_alvara_cadastrado_nao_registra_erro(monkeypatch):
    # vencimento_alvara None significa que o cliente nao tem alvara
    # cadastrado — o codigo so valida vencimento quando existe uma data.
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(
        valida_cliente, "resgatar_cliente",
        lambda cnpj: {
            "situacao_entidade": "Ativo",
            "razao_social": "Cliente Teste LTDA",
            "cnpj": cnpj,
            "vencimento_alvara": None,
        },
    )

    pedido = criar_pedido()
    valida_cliente.valida_clientes(pedido)

    assert erros == []
