"""Serviços automáticos (OL_Services) x layout da indústria.

Bug corrigido: retornos/espelhos/cancelados reservavam o pedido ("Aguardando X"
e depois "X Sendo Gerado") ANTES de saber se o layout da indústria gera aquele
arquivo. Com um layout sem implementação (FocoPDV, TudoFarma) o pedido ficava
travado em "Sendo Gerado" até a trava expirar — e a cada execução de novo.
Agora a indústria é pulada antes de qualquer consulta ou reserva.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ_OL_SERVICES = Path(__file__).resolve().parent.parent / "OL_Services"
if str(RAIZ_OL_SERVICES) not in sys.path:
    sys.path.insert(0, str(RAIZ_OL_SERVICES))

import cancelados  # noqa: E402
import espelhos  # noqa: E402
import retornos  # noqa: E402
from ol_core.layouts import Operacao, industria_suporta  # noqa: E402
from ol_core.models.enums.tipo_layout import TipoLayout  # noqa: E402

# serviço -> (função que busca os pedidos do ERP, método do LayouFactory)
SERVICOS = {
    retornos: ("verifica_arquivos_transmitidos", "gerar_retorno"),
    espelhos: ("verificar_emissao_titulos", "gerar_espelho"),
    cancelados: ("verifica_arquivos_cancelados", "gerar_cancelado"),
}


def _industria(tipo_layout):
    return SimpleNamespace(nome="Ind", id_bbs=1, tipo_layout=tipo_layout)


def _espionar(monkeypatch, servico, pedidos):
    chamadas = []
    busca, gerar = SERVICOS[servico]
    monkeypatch.setattr(servico, busca, lambda *a: chamadas.append("busca") or pedidos)
    monkeypatch.setattr(
        servico, "reservar_status_pedido",
        lambda numero, status, status_esperado=None: chamadas.append(("reserva", status)) or True,
    )
    monkeypatch.setattr(servico, "verifica_pedido_existente", lambda nome: True)
    # espelhos exige dados do pedido (truthy); retornos/cancelados só atualizam se houver.
    monkeypatch.setattr(servico, "verifica_dados_pedido", lambda numero: 1)
    opcionais = ("atualizar_dados_pedido", "verificar_tipo_de_arquivo_existente",
                 "verificar_espelho_existente", "verificar_cancelado_existente")
    for nome in opcionais:
        if hasattr(servico, nome):
            monkeypatch.setattr(servico, nome, lambda *a: None)
    monkeypatch.setattr(servico.LayouFactory, gerar, staticmethod(lambda *a: chamadas.append("gerou")))
    return chamadas


@pytest.mark.parametrize("servico", list(SERVICOS), ids=lambda m: m.__name__)
@pytest.mark.parametrize("layout", [TipoLayout.FOCOPDV, TipoLayout.TUDOFARMA, None])
def test_layout_sem_implementacao_nao_toca_em_nenhum_pedido(monkeypatch, servico, layout):
    pedido = SimpleNamespace(numero_pedido_ol="PED1", nome_arquivo="PED1.txt")
    chamadas = _espionar(monkeypatch, servico, [pedido])

    servico.processar_industria(_industria(layout))

    assert chamadas == []  # nem consulta o ERP, nem reserva, nem gera


@pytest.mark.parametrize("servico", list(SERVICOS), ids=lambda m: m.__name__)
def test_layout_closeup_segue_o_fluxo_normal(monkeypatch, servico):
    pedido = SimpleNamespace(numero_pedido_ol="PED1", nome_arquivo="PED1.txt")
    chamadas = _espionar(monkeypatch, servico, [pedido])

    servico.processar_industria(_industria(TipoLayout.CLOSEUP))

    assert chamadas[0] == "busca"
    assert [c for c in chamadas if isinstance(c, tuple)]  # reservou (Aguardando + Sendo Gerado)
    assert chamadas[-1] == "gerou"


@pytest.mark.parametrize("operacao", list(Operacao))
def test_industria_suporta(operacao):
    assert industria_suporta(_industria(TipoLayout.CLOSEUP), operacao) is True
    assert industria_suporta(_industria(TipoLayout.FOCOPDV), operacao) is False
    assert industria_suporta(_industria(None), operacao) is False
