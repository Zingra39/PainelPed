"""Testes de ol_core.validators.valida_pedido.

O arquivo tem duas funções agora:
- valida_valor_total_pedido(pedido, cond) — a validação de valor mínimo que
  antes se chamava só "valida_pedido".
- valida_pedido(pedido, id_cond_mae) — o novo orquestrador (chamado direto
  por import_service.py), que roda valida_clientes + valida_valor_total_pedido
  + valida_produto, com seu próprio try/except registrando uma ocorrência
  ERRO se algo escapar de tudo.
"""
import pytest

from ol_core.validators import valida_pedido as valida_pedido_mod
from ol_core.models.enums.tipo_severidade import TipoSeveridade
from .conftest import criar_pedido


def _preparar_captura_de_erros(monkeypatch):
    erros_registrados = []
    monkeypatch.setattr(
        valida_pedido_mod, "registrar_ocorrencia",
        lambda erro: erros_registrados.append(erro),
    )
    return erros_registrados


# --------------------------------------------------------------------- valida_valor_total_pedido

def test_quando_e_o_primeiro_pedido_do_cliente_nao_valida_valor_minimo(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(valida_pedido_mod, "verificar_primeiro_pedido", lambda cnpj, data: True)
    monkeypatch.setattr(valida_pedido_mod, "verificar_valor_pedido_minimo", lambda cond: 99999.0)

    pedido = criar_pedido(valor_total=1.0)
    valida_pedido_mod.valida_valor_total_pedido(pedido, cond=3692)

    assert erros == []


def test_pedido_nao_e_o_primeiro_e_valor_abaixo_do_minimo_registra_ocorrencia_info(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(valida_pedido_mod, "verificar_primeiro_pedido", lambda cnpj, data: False)
    monkeypatch.setattr(valida_pedido_mod, "verificar_valor_pedido_minimo", lambda cond: 200.0)

    pedido = criar_pedido(valor_total=100.0)
    valida_pedido_mod.valida_valor_total_pedido(pedido, cond=3692)

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.INFO.value
    assert "abaixo do mínimo" in erros[0].descricao


def test_pedido_nao_e_o_primeiro_mas_valor_atinge_o_minimo_nao_registra_ocorrencia(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(valida_pedido_mod, "verificar_primeiro_pedido", lambda cnpj, data: False)
    monkeypatch.setattr(valida_pedido_mod, "verificar_valor_pedido_minimo", lambda cond: 500.0)

    pedido = criar_pedido(valor_total=500.0)
    valida_pedido_mod.valida_valor_total_pedido(pedido, cond=3692)

    assert erros == []


def test_condicao_sem_valor_minimo_configurado_nao_deveria_gerar_ocorrencia(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(valida_pedido_mod, "verificar_primeiro_pedido", lambda cnpj, data: False)
    monkeypatch.setattr(valida_pedido_mod, "verificar_valor_pedido_minimo", lambda cond: 0)

    pedido = criar_pedido(valor_total=500.0)
    valida_pedido_mod.valida_valor_total_pedido(pedido, cond=3692)

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.ALERTA.value
    assert "Minimo da condição não configurado ou não encontrado para a condição" in erros[0].descricao


def test_valor_total_pedido_nulo_nao_quebra_e_nao_registra_ocorrencia(monkeypatch):
    erros = _preparar_captura_de_erros(monkeypatch)

    pedido = criar_pedido(valor_total=None)
    valida_pedido_mod.valida_valor_total_pedido(pedido, cond=3692)

    assert erros == []


# --------------------------------------------------------------------- valida_pedido (orquestrador)

def test_valida_pedido_chama_clientes_valor_total_e_produtos(monkeypatch):
    chamadas = []
    monkeypatch.setattr(valida_pedido_mod, "valida_clientes", lambda pedido: chamadas.append("clientes"))
    monkeypatch.setattr(
        valida_pedido_mod, "valida_valor_total_pedido",
        lambda pedido, cond: chamadas.append("valor_total"),
    )
    monkeypatch.setattr(
        valida_pedido_mod, "valida_produto",
        lambda numero_ol, itens: chamadas.append("produto"),
    )

    pedido = criar_pedido()
    valida_pedido_mod.valida_pedido(pedido, id_cond_mae=3692)

    assert chamadas == ["clientes", "valor_total", "produto"]


def test_valida_pedido_sem_numero_pedido_ol_nao_chama_valida_produto(monkeypatch):
    chamou_produto = []
    monkeypatch.setattr(valida_pedido_mod, "valida_clientes", lambda pedido: None)
    monkeypatch.setattr(valida_pedido_mod, "valida_valor_total_pedido", lambda pedido, cond: None)
    monkeypatch.setattr(
        valida_pedido_mod, "valida_produto",
        lambda numero_ol, itens: chamou_produto.append(True),
    )

    pedido = criar_pedido(numero_pedido_ol=None)
    valida_pedido_mod.valida_pedido(pedido, id_cond_mae=3692)

    assert chamou_produto == []


def test_valida_pedido_registra_ocorrencia_erro_se_algo_escapar(monkeypatch):
    # Rede de seguranca: se valida_clientes/valida_valor_total_pedido/valida_produto
    # deixarem escapar uma excecao nao tratada, valida_pedido() ainda registra uma
    # ocorrencia ERRO em vez de so deixar a excecao subir sem rastro.
    erros = _preparar_captura_de_erros(monkeypatch)
    monkeypatch.setattr(
        valida_pedido_mod, "valida_clientes",
        lambda pedido: (_ for _ in ()).throw(RuntimeError("falha simulada")),
    )

    pedido = criar_pedido()
    valida_pedido_mod.valida_pedido(pedido, id_cond_mae=3692)

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.ERRO.value
    assert "Erro ao validar pedido" in erros[0].descricao
