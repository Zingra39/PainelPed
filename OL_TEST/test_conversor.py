"""Testes de ol_core.utils.conversor.

Foco nas funcoes de conversao numerica (usadas em toda a geracao de
arquivos de retorno/espelho/cancelamento) e na leitura do arquivo de
pedido de layout Closeup (posicoes fixas de coluna).
"""
import pytest

from ol_core.utils import conversor


# --------------------------------------------------------------------- conversao de desconto (string <-> float)

@pytest.mark.parametrize("texto, valor_esperado", [
    ("08666", 86.66),
    ("00000", 0.0),
    ("10000", 100.0),
    ("00050", 0.5),
])
def test_converter_desconto_str_float(texto, valor_esperado):
    assert conversor.converter_desconto_str_float(texto) == valor_esperado


def test_converter_desconto_str_float_com_tamanho_errado_estoura_value_error():
    with pytest.raises(ValueError):
        conversor.converter_desconto_str_float("123")


@pytest.mark.parametrize("valor, texto_esperado", [
    (86.66, "08666"),
    (0.0, "00000"),
    (100.0, "10000"),
    (0.5, "00050"),
])
def test_converter_desconto_float_str(valor, texto_esperado):
    assert conversor.converter_desconto_float_str(valor) == texto_esperado


def test_ida_e_volta_str_float_str_preserva_o_valor():
    original = "03750"
    valor = conversor.converter_desconto_str_float(original)
    volta = conversor.converter_desconto_float_str(valor)
    assert volta == original


# --------------------------------------------------------------------- converter_arquivo_closeup
#
# O layout Closeup usa posicoes fixas de coluna (sem separador). Pra montar
# uma linha sintetica valida, criamos um "buffer" de 100 espacos e
# preenchemos so as posicoes que a funcao realmente le — assim cada campo
# fica exatamente na coluna que converter_arquivo_closeup espera.

TAMANHO_LINHA = 100


def _linha_cabecalho(cnpj_cliente="12345678000199", numero_pedido="00000000000000000001"):
    # posicoes: [0]=tipo de registro, [1:16]=cnpj (15), [16:36]=numero_pedido (20)
    linha = list(" " * TAMANHO_LINHA)
    linha[0] = "1"
    linha[1:16] = list(cnpj_cliente.rjust(15))
    linha[16:36] = list(numero_pedido.ljust(20)[:20])
    return "".join(linha)


def _linha_item(numero_pedido="00000000000000000001", ean="7890000000001", quantidade="00010",
                 desconto="00000", id_cond="03692"):
    # posicoes: [1:21]=numero_pedido (20), [21:34]=ean (13), [34:39]=quantidade (5),
    # [43:48]=desconto (5), [93:98]=id_cond (5)
    linha = list(" " * TAMANHO_LINHA)
    linha[0] = "2"
    linha[1:21] = list(numero_pedido.ljust(20)[:20])
    linha[21:34] = list(ean.ljust(13)[:13])
    linha[34:39] = list(quantidade.rjust(5, "0")[:5])
    linha[43:48] = list(desconto.rjust(5, "0")[:5])
    linha[93:98] = list(id_cond.rjust(5, "0")[:5])
    return "".join(linha)


def _linha_rodape():
    return "9" + " " * (TAMANHO_LINHA - 1)


def _industria_dummy(tmp_path, **dados):
    from .conftest import criar_industria
    return criar_industria(tmp_path, **dados)


def test_converter_arquivo_closeup_monta_pedido_e_itens_a_partir_do_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(
        conversor, "resgatar_produto",
        lambda ean: {"preco": 12.5, "codigo_produto": 555},
    )

    caminho = tmp_path / "PEDIDO_00000000000000000001.txt"
    conteudo = "\n".join([_linha_cabecalho(), _linha_item(), _linha_rodape()])
    caminho.write_text(conteudo, encoding="utf-8")

    industria = _industria_dummy(tmp_path)
    pedido = conversor.converter_arquivo_closeup(industria, str(caminho))

    assert pedido is not None
    assert pedido.cnpj_cliente == "12345678000199"
    assert len(pedido.itens) == 1
    assert pedido.itens[0].ean == "7890000000001"
    assert pedido.itens[0].quantidade_solicitada == 10
    assert pedido.itens[0].preco == 12.5
    assert pedido.itens[0].codigo_produto == 555
    assert pedido.itens[0].id_cond == 3692


def test_converter_arquivo_closeup_produto_nao_cadastrado_usa_preco_e_codigo_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(conversor, "resgatar_produto", lambda ean: None)

    caminho = tmp_path / "PEDIDO_00000000000000000001.txt"
    conteudo = "\n".join([_linha_cabecalho(), _linha_item(), _linha_rodape()])
    caminho.write_text(conteudo, encoding="utf-8")

    industria = _industria_dummy(tmp_path)
    pedido = conversor.converter_arquivo_closeup(industria, str(caminho))

    assert pedido.itens[0].preco == 0
    assert pedido.itens[0].codigo_produto == 0


def test_converter_arquivo_closeup_arquivo_curto_demais_envia_para_pasta_de_erro(tmp_path, monkeypatch):
    chamadas = []
    monkeypatch.setattr(conversor, "envia_arquivo_para_pasta", lambda origem, destino: chamadas.append(destino))

    caminho = tmp_path / "PEDIDO_TESTE.txt"
    caminho.write_text(_linha_cabecalho(), encoding="utf-8")  # só o cabeçalho, sem item nem rodapé

    industria = _industria_dummy(tmp_path, pasta_erro=str(tmp_path / "erro"))
    resultado = conversor.converter_arquivo_closeup(industria, str(caminho))

    assert resultado is None
    assert chamadas == [industria.pasta_erro]  # envia_arquivo_para_pasta recebe o Path, não str


def test_converter_arquivo_closeup_arquivo_inexistente_retorna_none(tmp_path):
    industria = _industria_dummy(tmp_path)
    resultado = conversor.converter_arquivo_closeup(industria, str(tmp_path / "nao_existe.txt"))
    assert resultado is None
