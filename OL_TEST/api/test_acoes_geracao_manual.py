"""operacoes.acoes_de_geracao_manual — campos `pode_gerar_*` que a tela lê.

A tela (OL_Web/src/lib/statusConfig.ts) tinha a própria cópia das listas de
status. Agora a regra mora só na API; este teste garante que, para indústria
CloseUp e pedido não faturado, o resultado é exatamente o que a tela fazia, e
que as únicas diferenças são as intencionais (layout sem implementação e
cancelamento de pedido já faturado — que a geração recusaria de todo jeito).
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services import operacoes
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.enums.tipo_status_oper import TipoStatusOper

# Cópia da regra que estava na tela, para comparação.
TELA_RETORNO = ['Retorno Gerado', 'Espelho Gerado', 'Cancelamento Gerado', 'Falha no Retorno']
TELA_ESPELHO = ['Espelho Gerado', 'Falha no Espelho']
TELA_CANCELAMENTO = ['Cancelamento Gerado', 'Falha no Cancelamento']

TODOS_STATUS = [s.value for s in TipoStatusOper] + [None]


def _pedido(status, layout="closeup", status_erp=TipoStatusErp.AGUARDANDO_FATURAMENTO.value, **extra):
    padrao = dict(
        status_operacional=status,
        status_erp=status_erp,
        industria=SimpleNamespace(layout=layout) if layout is not False else None,
        transmitido_em=None,
        arquivos=[],
    )
    padrao.update(extra)
    return SimpleNamespace(**padrao)


@pytest.mark.parametrize("status", TODOS_STATUS)
def test_closeup_nao_faturado_igual_a_regra_que_estava_na_tela(status):
    acoes = operacoes.acoes_de_geracao_manual(_pedido(status))

    assert acoes == {
        "pode_gerar_retorno": status in TELA_RETORNO,
        "pode_gerar_espelho": status in TELA_ESPELHO,
        "pode_gerar_cancelamento": status in TELA_CANCELAMENTO,
    }


def test_retorno_liberado_por_atraso_libera_o_botao():
    pedido = _pedido(
        TipoStatusOper.TRANSMITIDO.value,
        status_erp=TipoStatusErp.TRANSMITIDO.value,
        transmitido_em=datetime.now() - timedelta(hours=2),
    )

    assert operacoes.retorno_manual_liberado_por_atraso(pedido) is True
    assert operacoes.acoes_de_geracao_manual(pedido)["pode_gerar_retorno"] is True


@pytest.mark.parametrize("status", TELA_CANCELAMENTO)
def test_pedido_faturado_nao_oferece_cancelamento(status):
    pedido = _pedido(status, status_erp=TipoStatusErp.PROCESSO_CONCLUIDO.value)

    assert operacoes.acoes_de_geracao_manual(pedido)["pode_gerar_cancelamento"] is False


@pytest.mark.parametrize("layout", ["focopdv", "tudofarma", None, "desconhecido", False])
@pytest.mark.parametrize("status", ["Retorno Gerado", "Espelho Gerado", "Cancelamento Gerado"])
def test_layout_sem_implementacao_ou_sem_industria_nao_oferece_nada(layout, status):
    acoes = operacoes.acoes_de_geracao_manual(_pedido(status, layout=layout))

    assert acoes == {"pode_gerar_retorno": False, "pode_gerar_espelho": False, "pode_gerar_cancelamento": False}
