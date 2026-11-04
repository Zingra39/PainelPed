"""
Geração manual de Espelho e Cancelamento após falha ("Falha no Espelho" /
"Falha no Cancelamento"): a nova tentativa é só manual (o serviço automático
não reprocessa), e a trava "X Sendo Gerado" impede execuções concorrentes.

Mesma infra de test_operacoes_retorno.py: SQLite em memória + funções de
infraestrutura (ERP, geradores, atualizar_status_pedido) mockadas.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services import operacoes
from app.services.operacoes import geracao
from ol_core.layouts import closeup as layout_closeup  # a geração passa pelo layout registrado
from ol_core.models.enums.tipo_layout import TipoLayout
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from .conftest import criar_pedido_e_industria


def _stub_espelho(monkeypatch, gerar_ok=True):
    monkeypatch.setattr(geracao, "_build_industria", lambda industria_db: SimpleNamespace(tipo_layout=TipoLayout.CLOSEUP))
    monkeypatch.setattr(
        geracao, "verificar_titulo",
        lambda nome: [SimpleNamespace(nome_arquivo="PEDIDO_TESTE.txt", data_emissao=datetime.now())],
    )
    monkeypatch.setattr(layout_closeup, "gerar_espelho_closeup", lambda *a, **kw: gerar_ok)
    chamados: list[str] = []
    monkeypatch.setattr(geracao, "atualizar_status_pedido", lambda n, s: chamados.append(s))
    monkeypatch.setattr(geracao, "exigir_cnpj_distribuidor", lambda: "11222333000181")
    monkeypatch.setattr(geracao, "reservar_status_pedido", lambda n, s, status_esperado=None: chamados.append(s) or True)
    return chamados


def _stub_cancelamento(monkeypatch, gerar_ok=True):
    monkeypatch.setattr(
        geracao, "_build_industria",
        lambda industria_db: SimpleNamespace(tipo_layout=TipoLayout.CLOSEUP, pasta_envio_cancelamento="x"),
    )
    monkeypatch.setattr(geracao, "_build_pedido", lambda pedido_db: SimpleNamespace())
    monkeypatch.setattr(
        geracao, "verifica_pedido",
        lambda n: [SimpleNamespace(codigo_interno_pedido=1, cod_situacao="0", data_cancelamento=datetime.now(), quem_cancelou="x")],
    )
    monkeypatch.setattr(layout_closeup, "gerar_cancelado_closeup", lambda *a, **kw: gerar_ok)
    chamados: list[str] = []
    monkeypatch.setattr(geracao, "atualizar_status_pedido", lambda n, s: chamados.append(s))
    monkeypatch.setattr(geracao, "exigir_cnpj_distribuidor", lambda: "11222333000181")
    monkeypatch.setattr(geracao, "reservar_status_pedido", lambda n, s, status_esperado=None: chamados.append(s) or True)
    return chamados


# ------------------------------------------------------------------ espelho

@pytest.mark.parametrize("status_inicial", [TipoStatusOper.ESPELHO.value, TipoStatusOper.FALHA_ESPELHO.value])
def test_espelho_permitido_em_gerado_ou_falha(sessao_teste, monkeypatch, status_inicial):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=status_inicial)
    chamados = _stub_espelho(monkeypatch)

    resultado = operacoes.executar_gerar_espelho(pedido, id_usuario=1)

    assert resultado["sucesso"] is True
    assert chamados == [TipoStatusOper.GERANDO_ESPELHO.value, TipoStatusOper.ESPELHO.value]


def test_espelho_falha_de_novo_apos_falha_nao_vira_espelho_gerado(sessao_teste, monkeypatch):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=TipoStatusOper.FALHA_ESPELHO.value)
    chamados = _stub_espelho(monkeypatch, gerar_ok=False)

    with pytest.raises(RuntimeError):
        operacoes.executar_gerar_espelho(pedido, id_usuario=1)

    assert chamados == [TipoStatusOper.GERANDO_ESPELHO.value, TipoStatusOper.FALHA_ESPELHO.value]


@pytest.mark.parametrize("status_invalido", ["Importado", "Verificar", "Falha", TipoStatusOper.FALHA_RETORNO.value])
def test_espelho_status_nao_permitido_levanta_value_error(sessao_teste, monkeypatch, status_invalido):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=status_invalido)
    chamados = _stub_espelho(monkeypatch)

    with pytest.raises(ValueError):
        operacoes.executar_gerar_espelho(pedido, id_usuario=1)

    assert chamados == []


@pytest.mark.parametrize("status_gerando", [
    TipoStatusOper.GERANDO_RETORNO.value, TipoStatusOper.GERANDO_ESPELHO.value, TipoStatusOper.GERANDO_CANCELAMENTO.value,
])
def test_espelho_bloqueado_enquanto_geracao_em_curso(sessao_teste, monkeypatch, status_gerando):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=status_gerando)
    chamados = _stub_espelho(monkeypatch)

    with pytest.raises(ValueError, match="Aguarde"):
        operacoes.executar_gerar_espelho(pedido, id_usuario=1)

    assert chamados == []


# ------------------------------------------------------------- cancelamento

@pytest.mark.parametrize("status_inicial", [TipoStatusOper.CANCELADO.value, TipoStatusOper.FALHA_CANCELAMENTO.value])
def test_cancelamento_permitido_em_gerado_ou_falha(sessao_teste, monkeypatch, status_inicial):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=status_inicial)
    chamados = _stub_cancelamento(monkeypatch)

    resultado = operacoes.executar_cancelamento(pedido, id_usuario=1)

    assert resultado["sucesso"] is True
    assert chamados == [TipoStatusOper.GERANDO_CANCELAMENTO.value, TipoStatusOper.CANCELADO.value]


def test_cancelamento_falha_de_novo_apos_falha_nao_vira_cancelamento_gerado(sessao_teste, monkeypatch):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=TipoStatusOper.FALHA_CANCELAMENTO.value)
    chamados = _stub_cancelamento(monkeypatch, gerar_ok=False)

    with pytest.raises(RuntimeError):
        operacoes.executar_cancelamento(pedido, id_usuario=1)

    assert chamados == [TipoStatusOper.GERANDO_CANCELAMENTO.value, TipoStatusOper.FALHA_CANCELAMENTO.value]


@pytest.mark.parametrize("status_gerando", [
    TipoStatusOper.GERANDO_RETORNO.value, TipoStatusOper.GERANDO_ESPELHO.value, TipoStatusOper.GERANDO_CANCELAMENTO.value,
])
def test_cancelamento_bloqueado_enquanto_geracao_em_curso(sessao_teste, monkeypatch, status_gerando):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=status_gerando)
    chamados = _stub_cancelamento(monkeypatch)

    with pytest.raises(ValueError, match="Aguarde"):
        operacoes.executar_cancelamento(pedido, id_usuario=1)

    assert chamados == []


# ------------------------------------------------------------- cancelamento x status_erp
# Correção: o status_erp era comparado em minúsculas com uma lista em
# maiúsculas/minúsculas misturadas — só "Transmitido" passava. Agora só o
# pedido já faturado ("Pedido Concluido") é recusado.

@pytest.mark.parametrize("status_erp", [
    TipoStatusErp.NAO_TRANSMITIDO.value,
    TipoStatusErp.TRANSMITIDO.value,
    TipoStatusErp.AGUARDANDO_FATURAMENTO.value,
    TipoStatusErp.PEDIDO_CANCELADO.value,  # onde o pedido fica após um cancelamento gerado: permite regerar
    None,
])
def test_cancelamento_liberado_para_status_erp_nao_faturado(sessao_teste, monkeypatch, status_erp):
    pedido = criar_pedido_e_industria(
        sessao_teste, status_operacional=TipoStatusOper.CANCELADO.value, status_erp=status_erp,
    )
    chamados = _stub_cancelamento(monkeypatch)

    resultado = operacoes.executar_cancelamento(pedido, id_usuario=1)

    assert resultado["sucesso"] is True
    assert chamados == [TipoStatusOper.GERANDO_CANCELAMENTO.value, TipoStatusOper.CANCELADO.value]


@pytest.mark.parametrize("status_erp", [TipoStatusErp.PROCESSO_CONCLUIDO.value, "pedido concluido"])
def test_cancelamento_recusado_para_pedido_ja_faturado(sessao_teste, monkeypatch, status_erp):
    pedido = criar_pedido_e_industria(
        sessao_teste, status_operacional=TipoStatusOper.FALHA_CANCELAMENTO.value, status_erp=status_erp,
    )
    chamados = _stub_cancelamento(monkeypatch)

    with pytest.raises(ValueError, match="diretamente no ERP"):
        operacoes.executar_cancelamento(pedido, id_usuario=1)

    # Reservou e, com a recusa, voltou ao status de antes.
    assert chamados == [TipoStatusOper.GERANDO_CANCELAMENTO.value, TipoStatusOper.FALHA_CANCELAMENTO.value]


# ------------------------------------------------------------- layout da indústria
# A geração manual passa pelo registro de layouts: layout sem implementação é
# recusado com mensagem clara e o pedido volta ao status de antes (antes a API
# chamava as funções do CloseUp direto, qualquer que fosse o layout).

@pytest.mark.parametrize("layout", [TipoLayout.FOCOPDV, TipoLayout.TUDOFARMA])
def test_espelho_de_industria_com_layout_sem_implementacao_e_recusado(sessao_teste, monkeypatch, layout):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=TipoStatusOper.ESPELHO.value)
    chamados = _stub_espelho(monkeypatch)
    monkeypatch.setattr(geracao, "_build_industria", lambda industria_db: SimpleNamespace(tipo_layout=layout))
    gerados = []
    monkeypatch.setattr(layout_closeup, "gerar_espelho_closeup", lambda *a, **kw: gerados.append(1) or True)

    with pytest.raises(ValueError, match="Layout desconhecido"):
        operacoes.executar_gerar_espelho(pedido, id_usuario=1)

    assert gerados == []  # não gerou no formato CloseUp
    assert chamados == [TipoStatusOper.GERANDO_ESPELHO.value, TipoStatusOper.ESPELHO.value]


def test_cancelamento_de_industria_com_layout_sem_implementacao_e_recusado(sessao_teste, monkeypatch):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=TipoStatusOper.CANCELADO.value)
    chamados = _stub_cancelamento(monkeypatch)
    monkeypatch.setattr(
        geracao, "_build_industria",
        lambda industria_db: SimpleNamespace(tipo_layout=TipoLayout.FOCOPDV, pasta_envio_cancelamento="x"),
    )

    with pytest.raises(ValueError, match="Layout desconhecido"):
        operacoes.executar_cancelamento(pedido, id_usuario=1)

    assert chamados == [TipoStatusOper.GERANDO_CANCELAMENTO.value, TipoStatusOper.CANCELADO.value]
