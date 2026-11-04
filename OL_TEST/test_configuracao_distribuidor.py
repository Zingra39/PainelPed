"""I10: filiais de estoque e CNPJ do distribuidor saíram do código e vêm da
tabela `parametro` (tela de Parametrização). Nada aqui toca MySQL ou ERP."""
import pandas as pd
import pytest

from ol_core.database.mysql import contexto_parametros
from ol_core.database.sqlserver import contexto_produto


# ------------------------------------------------------------------ parâmetros

@pytest.mark.parametrize("valor, esperado", [
    (None, []),
    ("", []),
    ("12328", [12328]),
    ("12328, 12329", [12328, 12329]),
    ("12328;12329 12330", [12328, 12329, 12330]),
    ("12328,12328", [12328]),
    ("12328,abc,0,-1", [12328]),
])
def test_interpretar_filiais(valor, esperado):
    assert contexto_parametros.interpretar_filiais(valor) == esperado


def test_cnpj_distribuidor_tira_mascara_e_trata_vazio_como_nao_configurado(monkeypatch):
    monkeypatch.setattr(contexto_parametros, "obter_valor_parametro", lambda chave: "11.222.333/0001-81")
    assert contexto_parametros.cnpj_distribuidor() == "11222333000181"

    monkeypatch.setattr(contexto_parametros, "obter_valor_parametro", lambda chave: "  ")
    assert contexto_parametros.cnpj_distribuidor() is None
    with pytest.raises(contexto_parametros.ConfiguracaoAusente):
        contexto_parametros.exigir_cnpj_distribuidor()


def test_filiais_estoque_usa_cache_curto(monkeypatch):
    leituras = []
    monkeypatch.setattr(contexto_parametros, "_cache_filiais", None)
    monkeypatch.setattr(contexto_parametros, "obter_valor_parametro", lambda chave: leituras.append(chave) or "1,2")

    assert contexto_parametros.filiais_estoque() == [1, 2]
    assert contexto_parametros.filiais_estoque() == [1, 2]
    assert leituras == [contexto_parametros.CHAVE_FILIAIS_ESTOQUE]


# ------------------------------------------------------------------ consultas no ERP

def _capturar_consulta(monkeypatch, filiais, linhas=None):
    monkeypatch.setattr(contexto_produto, "filiais_estoque", lambda: list(filiais))
    chamadas = []

    def consultar(sql, params=None):
        chamadas.append((sql, params or {}))
        return pd.DataFrame(linhas if linhas is not None else {"estoque": [5]})

    monkeypatch.setattr(contexto_produto, "_consultar_dataframe", consultar)
    return chamadas


def test_estoque_do_item_soma_so_as_filiais_configuradas(monkeypatch):
    chamadas = _capturar_consulta(monkeypatch, [12328, 12329])

    assert contexto_produto.verifica_quantidade_que_sera_atendida(99) == 5

    sql, params = chamadas[0]
    assert "SUM(que.estoque - que.retencao)" in sql
    assert "que.cod_filial IN (:filial_0, :filial_1)" in sql
    assert "12328" not in sql  # valores vão como parâmetro, não no texto do SQL
    assert params == {"cod_produto": 99, "filial_0": 12328, "filial_1": 12329}


def test_estoque_do_item_sem_filial_configurada_nao_filtra_por_filial(monkeypatch):
    chamadas = _capturar_consulta(monkeypatch, [])

    contexto_produto.verifica_estoque_item_pedido(99)

    sql, params = chamadas[0]
    assert "cod_filial" not in sql
    assert params == {"cod_produto": 99}


def test_estoque_do_item_sem_linha_de_estoque_continua_none(monkeypatch):
    _capturar_consulta(monkeypatch, [12328], linhas={"estoque": []})
    assert contexto_produto.verifica_estoque_item(99) is None


def test_resgata_estoque_filtra_fornecedores_e_filiais_por_parametro(monkeypatch):
    chamadas = _capturar_consulta(monkeypatch, [12328], linhas={"Cod_barra": ["1"], "estoque_disponivel": [3]})

    contexto_produto.resgata_estoque([10423, 33929])

    sql, params = chamadas[0]
    assert "vwp.id_fornecedor in (:fornecedor_0, :fornecedor_1)" in sql
    assert "est.id_filial IN (:filial_0)" in sql
    assert "group by" in sql
    assert params == {"fornecedor_0": 10423, "fornecedor_1": 33929, "filial_0": 12328}


def test_resgata_estoque_sem_fornecedor_nao_consulta(monkeypatch):
    chamadas = _capturar_consulta(monkeypatch, [12328])
    assert contexto_produto.resgata_estoque([]) is None
    assert chamadas == []
