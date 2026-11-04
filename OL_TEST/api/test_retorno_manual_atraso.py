"""
Regra: se o pedido foi transmitido e o retorno não foi gerado até 1h depois,
a geração manual do retorno é liberada (operacoes.retorno_manual_liberado_por_atraso).

Mesma infra dos demais testes de OL_TEST/api: SQLite em memória + funções de
infraestrutura (ERP, gerador de retorno, atualizar_status_pedido) mockadas.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models import Arquivo
from app.routers import pedidos
from app.services import operacoes
from app.services.operacoes import geracao
from ol_core.layouts import closeup as layout_closeup  # a geração passa pelo layout registrado
from ol_core.models.enums.tipo_layout import TipoLayout
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from .conftest import criar_pedido_e_industria

TRANSMITIDO_ERP = TipoStatusErp.TRANSMITIDO.value


def _pedido_transmitido(sessao, minutos_atras, status_operacional=TipoStatusOper.TRANSMITIDO.value, **extra):
    return criar_pedido_e_industria(
        sessao,
        status_erp=TRANSMITIDO_ERP,
        status_operacional=status_operacional,
        transmitido_em=datetime.now() - timedelta(minutes=minutos_atras),
        **extra,
    )


def _stub_infra(monkeypatch, gerar_ok=True):
    monkeypatch.setattr(geracao, "_build_industria", lambda industria_db: SimpleNamespace(tipo_layout=TipoLayout.CLOSEUP))
    monkeypatch.setattr(geracao, "_build_pedido", lambda pedido_db: SimpleNamespace())
    monkeypatch.setattr(
        geracao, "verifica_pedido",
        lambda n: [SimpleNamespace(codigo_interno_pedido=1, cod_situacao="0", situacao="OK",
                                   data_cancelamento=None, quem_cancelou=None, data_faturamento=None)],
    )
    monkeypatch.setattr(layout_closeup, "gerar_retorno_closeup", lambda *a, **kw: gerar_ok)
    chamados: list[str] = []
    monkeypatch.setattr(geracao, "atualizar_status_pedido", lambda n, s: chamados.append(s))
    monkeypatch.setattr(geracao, "exigir_cnpj_distribuidor", lambda: "11222333000181")
    monkeypatch.setattr(geracao, "reservar_status_pedido", lambda n, s, status_esperado=None: chamados.append(s) or True)
    return chamados


# --------------------------------------------------------------- a regra

@pytest.mark.parametrize("status_op", [TipoStatusOper.TRANSMITIDO.value, TipoStatusOper.AGUARDANDO_RETORNO.value])
def test_libera_apos_1h(sessao_teste, status_op):
    pedido = _pedido_transmitido(sessao_teste, 61, status_operacional=status_op)
    assert operacoes.retorno_manual_liberado_por_atraso(pedido) is True


def test_nao_libera_antes_de_1h(sessao_teste):
    pedido = _pedido_transmitido(sessao_teste, 59)
    assert operacoes.retorno_manual_liberado_por_atraso(pedido) is False


def test_nao_libera_sem_transmitido_em(sessao_teste):
    pedido = criar_pedido_e_industria(
        sessao_teste, status_erp=TRANSMITIDO_ERP, status_operacional=TipoStatusOper.TRANSMITIDO.value,
    )
    assert operacoes.retorno_manual_liberado_por_atraso(pedido) is False


@pytest.mark.parametrize("status_erp", [
    TipoStatusErp.NAO_TRANSMITIDO.value,
    TipoStatusErp.AGUARDANDO_FATURAMENTO.value,
    TipoStatusErp.PROCESSO_CONCLUIDO.value,
    TipoStatusErp.PEDIDO_CANCELADO.value,
])
def test_nao_libera_fora_do_status_erp_transmitido(sessao_teste, status_erp):
    pedido = _pedido_transmitido(sessao_teste, 120)
    pedido.status_erp = status_erp
    assert operacoes.retorno_manual_liberado_por_atraso(pedido) is False


def test_nao_libera_se_retorno_ja_foi_gerado(sessao_teste):
    pedido = _pedido_transmitido(sessao_teste, 120)
    sessao_teste.add(Arquivo(
        numero_pedido_ol=pedido.numero_pedido_ol, nome="RETORNO_X.TXT", tipo="retorno",
        situacao=TipoStatusOper.RETORNO.value, criado_em=datetime.now(),
    ))
    sessao_teste.commit()
    sessao_teste.refresh(pedido)

    assert operacoes.retorno_manual_liberado_por_atraso(pedido) is False


# ------------------------------------------------------ a geração manual

def test_gerar_retorno_liberado_por_atraso_vai_para_retorno_gerado(sessao_teste, monkeypatch):
    pedido = _pedido_transmitido(sessao_teste, 90, status_operacional=TipoStatusOper.AGUARDANDO_RETORNO.value)
    chamados = _stub_infra(monkeypatch)

    resultado = operacoes.executar_gerar_retorno(pedido, id_usuario=1)

    assert resultado["sucesso"] is True
    assert chamados == [TipoStatusOper.GERANDO_RETORNO.value, TipoStatusOper.RETORNO.value]


def test_gerar_retorno_liberado_por_atraso_que_falha_volta_ao_status_anterior(sessao_teste, monkeypatch):
    pedido = _pedido_transmitido(sessao_teste, 90, status_operacional=TipoStatusOper.AGUARDANDO_RETORNO.value)
    chamados = _stub_infra(monkeypatch, gerar_ok=False)

    with pytest.raises(RuntimeError):
        operacoes.executar_gerar_retorno(pedido, id_usuario=1)

    assert chamados == [TipoStatusOper.GERANDO_RETORNO.value, TipoStatusOper.AGUARDANDO_RETORNO.value]


def test_gerar_retorno_antes_de_1h_continua_bloqueado(sessao_teste, monkeypatch):
    pedido = _pedido_transmitido(sessao_teste, 30)
    chamados = _stub_infra(monkeypatch)

    with pytest.raises(ValueError):
        operacoes.executar_gerar_retorno(pedido, id_usuario=1)

    assert chamados == []


def test_gerar_retorno_atrasado_respeita_a_trava_sendo_gerado(sessao_teste, monkeypatch):
    pedido = _pedido_transmitido(sessao_teste, 120, status_operacional=TipoStatusOper.GERANDO_RETORNO.value)
    chamados = _stub_infra(monkeypatch)

    with pytest.raises(ValueError, match="Aguarde"):
        operacoes.executar_gerar_retorno(pedido, id_usuario=1)

    assert chamados == []


# ------------------------------------------------------------------ a API

def test_rastreamento_expoe_retorno_manual_liberado(sessao_teste, montar_client):
    atrasado = _pedido_transmitido(sessao_teste, 120)
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    resposta = client.get("/pedidos/rastreamento")

    assert resposta.status_code == 200
    item = next(i for i in resposta.json()["items"] if i["id"] == atrasado.id)
    assert item["retorno_manual_liberado"] is True
