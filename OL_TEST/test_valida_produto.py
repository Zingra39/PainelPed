"""Testes de ol_core.validators.valida_produto.valida_produto.

A função mudou de assinatura: agora recebe o pedido inteiro (numero_ol +
lista de itens) de uma vez, em vez de um item por chamada — e tem seu
próprio try/except em volta do laço de itens, registrando uma ocorrência
CRÍTICA (com o EAN do item que falhou) se algo quebrar no meio do laço.

Pra manter os testes simples, a chamada interna pra valida_condicaos() é
sempre "desligada" via monkeypatch — quem testa valida_condicaos é o
test_valida_condicao.py, aqui o foco é só a lógica de produto.
"""
import decimal

import pytest

from ol_core.validators import valida_produto as valida_produto_mod
from ol_core.models.enums.tipo_severidade import TipoSeveridade
from .conftest import criar_item


def _preparar_ambiente(monkeypatch):
    """Captura os erros registrados e desliga a chamada a valida_condicaos
    (ela é testada separadamente em test_valida_condicao.py)."""
    erros_registrados = []
    monkeypatch.setattr(
        valida_produto_mod, "registrar_ocorrencia",
        lambda erro: erros_registrados.append(erro),
    )
    monkeypatch.setattr(valida_produto_mod, "valida_condicaos", lambda *args, **kwargs: None)
    return erros_registrados


def _produto_condicao_valida(**sobrescreve):
    """produto_condicao onde nenhuma regra é violada (usado como base)."""
    padrao = dict(
        desconto_negociado=0,
        qtd_desc_1=0,
        qtd_desc_2=0,
        qtd_desc_3=0,
        qtd_desc_4=0,
        desc_1=10,
        desc_2=15,
        desc_3=20,
        desc_4=25,
        desconto=0,
    )
    padrao.update(sobrescreve)
    return padrao


def test_lista_de_itens_vazia_registra_erro(monkeypatch):
    erros = _preparar_ambiente(monkeypatch)

    valida_produto_mod.valida_produto("PED0001", [])

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.ERRO.value
    assert "não possui produtos" in erros[0].descricao


def test_produto_nao_cadastrado_registra_erro(monkeypatch):
    erros = _preparar_ambiente(monkeypatch)
    monkeypatch.setattr(valida_produto_mod, "resgatar_produto", lambda ean: None)

    item = criar_item()
    valida_produto_mod.valida_produto(item.numero_pedido_ol, [item])

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.ERRO.value
    assert "não está cadastrado no Delage" in erros[0].descricao


def test_produto_sem_estoque_registra_ocorrencia_info(monkeypatch):
    erros = _preparar_ambiente(monkeypatch)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto",
        lambda ean: {"codigo_produto": 999, "descricao": "Produto Teste"},
    )
    monkeypatch.setattr(valida_produto_mod, "verifica_estoque_item", lambda codigo_produto: True)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto_na_condicao",
        lambda codigo_produto, id_cond: _produto_condicao_valida(),
    )

    item = criar_item()
    valida_produto_mod.valida_produto(item.numero_pedido_ol, [item])

    # Uma ocorrencia de "sem estoque" (o restante da condicao esta valido)
    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.INFO.value
    assert "não está em estoque" in erros[0].descricao


def test_produto_fora_da_condicao_registra_alerta(monkeypatch):
    erros = _preparar_ambiente(monkeypatch)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto",
        lambda ean: {"codigo_produto": 999, "descricao": "Produto Teste"},
    )
    monkeypatch.setattr(valida_produto_mod, "verifica_estoque_item", lambda codigo_produto: False)
    monkeypatch.setattr(valida_produto_mod, "resgatar_produto_na_condicao", lambda codigo_produto, id_cond: None)

    item = criar_item()
    valida_produto_mod.valida_produto(item.numero_pedido_ol, [item])

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.ALERTA.value
    assert "não está configurado na condição" in erros[0].descricao


def test_produto_dentro_de_tudo_valido_nao_registra_nenhum_erro(monkeypatch):
    erros = _preparar_ambiente(monkeypatch)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto",
        lambda ean: {"codigo_produto": 999, "descricao": "Produto Teste"},
    )
    monkeypatch.setattr(valida_produto_mod, "verifica_estoque_item", lambda codigo_produto: False)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto_na_condicao",
        lambda codigo_produto, id_cond: _produto_condicao_valida(),
    )

    item = criar_item(desconto=0)
    valida_produto_mod.valida_produto(item.numero_pedido_ol, [item])

    assert erros == []


def test_quantidade_abaixo_da_primeira_faixa_de_desconto_registra_alerta(monkeypatch):
    erros = _preparar_ambiente(monkeypatch)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto",
        lambda ean: {"codigo_produto": 999, "descricao": "Produto Teste"},
    )
    monkeypatch.setattr(valida_produto_mod, "verifica_estoque_item", lambda codigo_produto: False)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto_na_condicao",
        lambda codigo_produto, id_cond: _produto_condicao_valida(qtd_desc_1=100),
    )

    item = criar_item(quantidade_solicitada=10, quantidade_atendida=10, desconto=0)
    valida_produto_mod.valida_produto(item.numero_pedido_ol, [item])

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.ALERTA.value
    assert "menor que o configurado na condicao" in erros[0].descricao


def test_desconto_do_item_maior_que_o_da_faixa_1_registra_alerta(monkeypatch):
    erros = _preparar_ambiente(monkeypatch)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto",
        lambda ean: {"codigo_produto": 999, "descricao": "Produto Teste"},
    )
    monkeypatch.setattr(valida_produto_mod, "verifica_estoque_item", lambda codigo_produto: False)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto_na_condicao",
        lambda codigo_produto, id_cond: _produto_condicao_valida(qtd_desc_1=5, desc_1=10),
    )

    # quantidade cai na faixa 1 (>= 5 e < qtd_desc_2, que esta zerado / desligado)
    item = criar_item(quantidade_solicitada=10, quantidade_atendida=10, desconto=20)
    valida_produto_mod.valida_produto(item.numero_pedido_ol, [item])

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.ALERTA.value
    assert "Desconto do Produto Teste" in erros[0].descricao


def test_desconto_negociado_ativo_pula_validacao_de_faixas_progressivas(monkeypatch):
    # Quando desconto_negociado != 0, o bloco inteiro de faixas progressivas
    # e ignorado, mesmo com a quantidade fora de qualquer faixa.
    erros = _preparar_ambiente(monkeypatch)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto",
        lambda ean: {"codigo_produto": 999, "descricao": "Produto Teste"},
    )
    monkeypatch.setattr(valida_produto_mod, "verifica_estoque_item", lambda codigo_produto: False)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto_na_condicao",
        lambda codigo_produto, id_cond: _produto_condicao_valida(desconto_negociado=1, qtd_desc_1=100),
    )

    item = criar_item(quantidade_solicitada=1, quantidade_atendida=1, desconto=0)
    valida_produto_mod.valida_produto(item.numero_pedido_ol, [item])

    assert erros == []


def test_desconto_do_arquivo_maior_que_o_desconto_da_condicao_registra_alerta(monkeypatch):
    erros = _preparar_ambiente(monkeypatch)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto",
        lambda ean: {"codigo_produto": 999, "descricao": "Produto Teste"},
    )
    monkeypatch.setattr(valida_produto_mod, "verifica_estoque_item", lambda codigo_produto: False)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto_na_condicao",
        lambda codigo_produto, id_cond: _produto_condicao_valida(desconto=10),
    )

    item = criar_item(desconto=15)
    valida_produto_mod.valida_produto(item.numero_pedido_ol, [item])

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.ALERTA.value


def test_desconto_do_arquivo_igual_ao_da_condicao_nao_registra_erro(monkeypatch):
    # Confere que a comparacao usa arredondamento (decimal.Decimal com 2
    # casas), entao 10.0 e 10 devem ser tratados como iguais.
    erros = _preparar_ambiente(monkeypatch)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto",
        lambda ean: {"codigo_produto": 999, "descricao": "Produto Teste"},
    )
    monkeypatch.setattr(valida_produto_mod, "verifica_estoque_item", lambda codigo_produto: False)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto_na_condicao",
        lambda codigo_produto, id_cond: _produto_condicao_valida(desconto=10),
    )

    item = criar_item(desconto=10.0)
    valida_produto_mod.valida_produto(item.numero_pedido_ol, [item])

    assert erros == []


def test_varios_itens_validos_geram_uma_ocorrencia_por_item_com_problema(monkeypatch):
    erros = _preparar_ambiente(monkeypatch)
    monkeypatch.setattr(valida_produto_mod, "verifica_estoque_item", lambda codigo_produto: False)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto_na_condicao",
        lambda codigo_produto, id_cond: _produto_condicao_valida(),
    )

    def resgatar_produto(ean):
        # o item "999" nao esta cadastrado, os outros dois estao
        if ean == "produto-nao-cadastrado":
            return None
        return {"codigo_produto": 1, "descricao": "Produto Teste"}

    monkeypatch.setattr(valida_produto_mod, "resgatar_produto", resgatar_produto)

    itens = [
        criar_item(ean="produto-ok-1", desconto=0),
        criar_item(ean="produto-nao-cadastrado", desconto=0),
        criar_item(ean="produto-ok-2", desconto=0),
    ]

    valida_produto_mod.valida_produto("PED0001", itens)

    # todos os 3 itens sao avaliados nesse cenario (nenhum estoura excecao) —
    # so o item sem cadastro gera ocorrencia
    assert len(erros) == 1
    assert "produto-nao-cadastrado" in erros[0].descricao


def test_item_que_estoura_excecao_registra_ocorrencia_critica_com_o_ean(monkeypatch):
    # Este e o mecanismo de visibilidade que substituiu o log silencioso:
    # se algo quebrar no meio do laco, valida_produto() captura a excecao e
    # registra uma ocorrencia CRITICA citando o EAN do item que falhou — em
    # vez de so aparecer no log do servidor.
    erros = _preparar_ambiente(monkeypatch)

    def resgatar_produto_que_quebra(ean):
        raise RuntimeError("falha simulada consultando o ERP")

    monkeypatch.setattr(valida_produto_mod, "resgatar_produto", resgatar_produto_que_quebra)

    item = criar_item(ean="ean-que-quebra")
    valida_produto_mod.valida_produto(item.numero_pedido_ol, [item])

    assert len(erros) == 1
    assert erros[0].severidade == TipoSeveridade.CRITICO.value
    assert "ean-que-quebra" in erros[0].descricao


def test_item_que_quebra_no_meio_do_lote_nao_impede_os_itens_seguintes_de_serem_avaliados(monkeypatch):
    # CONFIRMADO CORRIGIDO: o try/except agora fica dentro do "for item in itens",
    # por item — um item que quebra gera sua propria ocorrencia CRITICA e o laco
    # segue pros itens seguintes, que sao avaliados normalmente.
    erros = _preparar_ambiente(monkeypatch)

    def resgatar_produto(ean):
        if ean == "ean-que-quebra":
            raise RuntimeError("falha simulada consultando o ERP")
        return None  # os itens seguintes, se avaliados, gerariam "produto nao cadastrado"

    monkeypatch.setattr(valida_produto_mod, "resgatar_produto", resgatar_produto)

    itens = [
        criar_item(ean="ean-que-quebra"),
        criar_item(ean="ean-nunca-avaliado-1"),
        criar_item(ean="ean-nunca-avaliado-2"),
    ]

    valida_produto_mod.valida_produto("PED0001", itens)

    # se a isolacao por item existisse, esperariamos 3 ocorrencias: a CRITICA do
    # item que quebrou + uma ERRO "nao cadastrado" pra cada um dos outros dois
    descricoes = [e.descricao for e in erros]
    assert any("ean-nunca-avaliado-1" in d for d in descricoes), (
        "o item apos o que quebrou deveria ter sido avaliado e gerado sua propria ocorrencia"
    )
    assert any("ean-nunca-avaliado-2" in d for d in descricoes), (
        "o segundo item apos o que quebrou deveria ter sido avaliado e gerado sua propria ocorrencia"
    )


# ------------------------------------------------------------------ vírgula decimal só nos percentuais
# Correção: o .replace('.', ',') era aplicado à mensagem inteira e alterava a
# descrição do produto ("Prod. A" virava "Prod, A").

def _produto_com_ponto(monkeypatch):
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto",
        lambda ean: {"codigo_produto": 999, "descricao": "DIPIRONA 500MG C/10 COMP. REV."},
    )
    monkeypatch.setattr(valida_produto_mod, "verifica_estoque_item", lambda codigo_produto: False)


def test_desconto_acima_da_faixa_preserva_pontos_da_descricao_e_usa_virgula_no_percentual(monkeypatch):
    erros = _preparar_ambiente(monkeypatch)
    _produto_com_ponto(monkeypatch)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto_na_condicao",
        lambda codigo_produto, id_cond: _produto_condicao_valida(qtd_desc_1=5, desc_1=10.5),
    )

    item = criar_item(quantidade_solicitada=10, quantidade_atendida=10, desconto=12.25)
    valida_produto_mod.valida_produto(item.numero_pedido_ol, [item])

    assert len(erros) == 1
    assert erros[0].descricao == (
        f"Desconto do DIPIRONA 500MG C/10 COMP. REV. - {item.ean} maior que o configurado na condicao "
        "(aplicado: 12,25%, limite: 10,50%)"
    )


def test_desconto_acima_do_maximo_da_condicao_preserva_pontos_da_descricao(monkeypatch):
    erros = _preparar_ambiente(monkeypatch)
    _produto_com_ponto(monkeypatch)
    monkeypatch.setattr(
        valida_produto_mod, "resgatar_produto_na_condicao",
        lambda codigo_produto, id_cond: _produto_condicao_valida(desconto_negociado=1, desconto=8),
    )

    item = criar_item(quantidade_solicitada=10, quantidade_atendida=10, desconto=9.5)
    valida_produto_mod.valida_produto(item.numero_pedido_ol, [item])

    assert len(erros) == 1
    assert "DIPIRONA 500MG C/10 COMP. REV." in erros[0].descricao
    assert "(aplicado: 9,50%, limite: 8,00%)" in erros[0].descricao
