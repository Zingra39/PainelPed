"""Testes de OL_Services/monta_arquivo_pedido.py e ambiente_local.py.

Nenhum teste toca o MySQL: as consultas são trocadas via monkeypatch no módulo
que as chama (convenção do conftest.py).
"""
import sys
from pathlib import Path

import pytest

RAIZ_OL_SERVICES = Path(__file__).resolve().parent.parent / "OL_Services"
if str(RAIZ_OL_SERVICES) not in sys.path:
    sys.path.insert(0, str(RAIZ_OL_SERVICES))

import ambiente_local  # noqa: E402
import monta_arquivo_pedido as m  # noqa: E402
from ol_core.utils import conversor  # noqa: E402

from .conftest import criar_industria  # noqa: E402

NUMERO = "2026102900123456787P"


def test_numero_de_teste_tem_20_posicoes():
    assert len(NUMERO) == 20


def test_cabecalho_tem_247_colunas_e_campos_nas_posicoes_do_layout():
    from datetime import datetime
    linha = m.monta_cabecalho(NUMERO, "57107095000164", datetime(2026, 10, 29), "30 60 90")
    assert len(linha) == 247
    assert linha[0] == "1"
    assert linha[1:16].strip() == "57107095000164"
    assert linha[16:36] == NUMERO
    assert linha[36:44] == "29102026"
    assert linha[44:47] == "000"
    assert linha[86:186].strip() == "30 60 90"


def test_item_tem_120_colunas_e_campos_nas_posicoes_do_layout():
    linha = m.monta_item(NUMERO, "7891234567895", 12, 3692, 86.66, 45.9)
    assert len(linha) == 120
    assert linha[0] == "2"
    assert linha[1:21] == NUMERO
    assert linha[21:34] == "7891234567895"
    assert linha[34:39] == "00012"
    assert linha[39:43] == "3692"
    assert linha[43:48] == "08666"
    assert linha[93:98] == "03692"
    assert linha[113:120] == "0004590"


def test_desconto_e_preco_sao_limitados_ao_campo():
    linha = m.monta_item(NUMERO, "7891234567895", 1, 0, 250, 999999)
    assert linha[43:48] == "09999"
    assert linha[113:120] == "9999999"


def test_rodape_tem_36_colunas():
    linha = m.monta_rodape(NUMERO, 3, 41)
    assert len(linha) == 36
    assert linha[21:26] == "00003"
    assert linha[26:36] == "0000000041"


def test_campo_numerico_que_nao_cabe_estoura():
    with pytest.raises(ValueError):
        m._n(123456, 5)


def _dados_falsos(monkeypatch):
    monkeypatch.setattr(m, "buscar_um", lambda sql, args=None: (
        {"cnpj_cliente": "57107095000164", "observacao": "prazo 30-60-90"}
        if "FROM pedido WHERE CHAR_LENGTH" in sql or "ORDER BY RAND" in sql else None
    ))
    monkeypatch.setattr(m, "buscar_todos", lambda sql, args=None: [
        {"ean": "7891234567895", "qtd": 10, "desconto": 12.5, "id_cond": 3692, "preco": 20.0},
        {"ean": "7899999999994", "qtd": 3, "desconto": 0, "id_cond": 0, "preco": 8.5},
    ])


def test_gerar_pedido_recusa_pasta_fora_de_ol_local(tmp_path, monkeypatch):
    _dados_falsos(monkeypatch)
    industria = criar_industria(tmp_path)  # pastas em tmp_path, fora de OL_LOCAL
    with pytest.raises(RuntimeError, match="fora de OL_LOCAL"):
        m.gerar_pedido_teste(industria)
    assert not list(tmp_path.rglob("PEDIDO_*.txt"))


def test_isolar_industria_move_todas_as_pastas_para_ol_local(tmp_path, monkeypatch):
    monkeypatch.setattr(ambiente_local, "RAIZ_OL_LOCAL", tmp_path / "OL_LOCAL")
    industria = criar_industria(tmp_path / "producao")
    ambiente_local.isolar_industria(industria)
    for pasta in ambiente_local._PASTAS:
        assert ambiente_local.esta_em_ol_local(getattr(industria, f"pasta_{pasta}"))


def test_arquivo_gerado_e_aceito_pelo_parser_closeup(tmp_path, monkeypatch):
    monkeypatch.setattr(ambiente_local, "RAIZ_OL_LOCAL", tmp_path / "OL_LOCAL")
    _dados_falsos(monkeypatch)
    industria = criar_industria(tmp_path / "producao")
    ambiente_local.isolar_industria(industria)

    caminho = m.gerar_pedido_teste(industria)

    assert caminho.parent == industria.pasta_envio
    numero = caminho.name.split("_")[1]
    assert len(numero) == 20 and numero.endswith("7P")

    monkeypatch.setattr(conversor, "resgatar_produto",
                        lambda ean: {"preco": 20.0, "codigo_produto": 111})
    pedido = conversor.converter_arquivo_closeup(industria, str(caminho))

    assert pedido is not None
    assert pedido.numero_pedido_ol == numero
    assert pedido.cnpj_cliente == "57107095000164"
    assert 1 <= len(pedido.itens) <= 2
    assert {i.ean for i in pedido.itens} <= {"7891234567895", "7899999999994"}
