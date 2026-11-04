import pytest

from ol_core.validators import validador
from .conftest import criar_item, criar_pedido


# --------------------------------------------------------------------- valida_ean

def test_valida_ean_com_codigo_produto_informado_retorna_o_proprio_ean():
    # Quando o item ja veio com codigo_produto preenchido, a funcao nem
    # deveria consultar o banco — so devolve o EAN recebido.
    resultado = validador.valida_ean("PED001", 999, "7890000000001")
    assert resultado == "7890000000001"


def test_valida_ean_sem_codigo_produto_e_sem_eans_encontrados_retorna_o_ean_original(monkeypatch):
    monkeypatch.setattr(validador, "verifica_tipo_ean", lambda codigo_produto: None)

    resultado = validador.valida_ean("PED001", None, "7890000000001")

    assert resultado == "7890000000001"


def test_valida_ean_escolhe_o_ean_que_ja_foi_coletado_no_pedido(monkeypatch):
    monkeypatch.setattr(validador, "verifica_tipo_ean", lambda codigo_produto: ["111", "222", "333"])
    # so o "222" esta marcado como ja coletado nesse pedido
    monkeypatch.setattr(
        validador, "verificar_ean_pedido_coletado",
        lambda numero_pedido, ean: ean == "222",
    )

    resultado = validador.valida_ean("PED001", 0, "ean-original")

    assert resultado == "222"


def test_valida_ean_sem_nenhum_ean_coletado_usa_o_primeiro_ean_valido_como_fallback(monkeypatch):
    monkeypatch.setattr(validador, "verifica_tipo_ean", lambda codigo_produto: ["111", "222"])
    monkeypatch.setattr(validador, "verificar_ean_pedido_coletado", lambda numero_pedido, ean: False)
    monkeypatch.setattr(validador, "verifica_primeiro_ean_valido", lambda codigo_produto: "999")

    resultado = validador.valida_ean("PED001", 0, "ean-original")

    assert resultado == "999"


# --------------------------------------------------------------------- valida_motivo — atalhos por cod_motivo

@pytest.mark.parametrize("cod_motivo, codigo_esperado", [
    (8, 125001),
    (10, 125001),
    (17, 125004),
    (4, 229994),
    (12, 221001),
    (7, 125004),
])
def test_valida_motivo_codigos_de_atalho_nao_consultam_o_banco(cod_motivo, codigo_esperado):
    # Esses codigos retornam direto, sem nenhuma consulta ao ERP — por isso
    # nao mockamos nada: se a funcao tentasse consultar o banco de verdade,
    # o teste ja quebraria por falta de conexao.
    item = criar_item(cod_motivo=cod_motivo)
    pedido = criar_pedido()

    resultado = validador.valida_motivo(item, pedido, "12345678000199")

    assert resultado == codigo_esperado


def test_valida_motivo_quantidade_atendida_diferente_da_solicitada_retorna_9():
    item = criar_item(cod_motivo=99, quantidade_solicitada=10, quantidade_atendida=5)
    pedido = criar_pedido()

    resultado = validador.valida_motivo(item, pedido, "12345678000199")

    assert resultado == 9


# --------------------------------------------------------------------- valida_motivo — cod_motivo == 0

@pytest.mark.parametrize("cod_situacao, codigo_esperado", [
    (10, 229994),
    (11, 229993),
    (8, 229996),
    (6, 229998),
    (9, 239011),
    (0, 0),
    (123, 0),  # situacao nao mapeada cai no "senao" -> 0
])
def test_valida_motivo_sem_motivo_usa_situacao_do_pedido(cod_situacao, codigo_esperado):
    item = criar_item(cod_motivo=0)
    pedido = criar_pedido(cod_situacao=cod_situacao)

    resultado = validador.valida_motivo(item, pedido, "12345678000199")

    assert resultado == codigo_esperado


# --------------------------------------------------------------------- valida_motivo — caminho completo

def test_valida_motivo_produto_sem_estoque_retorna_239004(monkeypatch):
    item = criar_item(cod_motivo=99, quantidade_solicitada=10, quantidade_atendida=10)
    pedido = criar_pedido()

    monkeypatch.setattr(validador, "verificar_condicao", lambda condicao: {"final": "9999-12-31"})
    monkeypatch.setattr(validador, "verifica_estoque_item_pedido", lambda codigo_produto: True)

    resultado = validador.valida_motivo(item, pedido, "12345678000199")

    assert resultado == 239004


def test_valida_motivo_condicao_vencida_retorna_221008(monkeypatch):
    from datetime import datetime, timedelta

    item = criar_item(cod_motivo=99, quantidade_solicitada=10, quantidade_atendida=10)
    pedido = criar_pedido()
    pedido.data_pedido = datetime.now()

    monkeypatch.setattr(
        validador, "verificar_condicao",
        lambda condicao: {"final": datetime.now() - timedelta(days=1)},
    )
    monkeypatch.setattr(validador, "verifica_estoque_item_pedido", lambda codigo_produto: False)

    resultado = validador.valida_motivo(item, pedido, "12345678000199")

    assert resultado == 221008


def test_valida_motivo_produto_sem_configuracao_na_condicao_retorna_125005(monkeypatch):
    from datetime import datetime, timedelta

    item = criar_item(cod_motivo=99, quantidade_solicitada=10, quantidade_atendida=10)
    pedido = criar_pedido()
    pedido.data_pedido = datetime.now() - timedelta(days=1)

    monkeypatch.setattr(
        validador, "verificar_condicao",
        lambda condicao: {"final": datetime.now() + timedelta(days=30), "todos_clientes": -1},
    )
    monkeypatch.setattr(validador, "verifica_estoque_item_pedido", lambda codigo_produto: False)
    monkeypatch.setattr(validador, "verificar_item_condicao", lambda codigo_produto, condicao: None)

    resultado = validador.valida_motivo(item, pedido, "12345678000199")

    assert resultado == 125005


def test_valida_motivo_preco_nulo_deveria_retornar_225004_sem_quebrar(monkeypatch):
    from datetime import datetime, timedelta

    item = criar_item(cod_motivo=2, quantidade_solicitada=10, quantidade_atendida=10, preco=None, desconto=0)
    pedido = criar_pedido()
    pedido.data_pedido = datetime.now() - timedelta(days=1)

    monkeypatch.setattr(
        validador, "verificar_condicao",
        lambda condicao: {"final": datetime.now() + timedelta(days=30), "todos_clientes": -1},
    )
    monkeypatch.setattr(validador, "verifica_estoque_item_pedido", lambda codigo_produto: False)
    monkeypatch.setattr(
        validador, "verificar_item_condicao",
        lambda codigo_produto, condicao: {"qtd_desc_1": None, "preco": None, "desconto": 100},
    )

    resultado = validador.valida_motivo(item, pedido, "12345678000199")

    codigo_ok = resultado == 225004

    assert codigo_ok
