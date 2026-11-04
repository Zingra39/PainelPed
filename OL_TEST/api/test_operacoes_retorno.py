"""
Testes de app.services.operacoes.executar_gerar_retorno — cobre o gate de
status (permite regenerar o retorno em 'Retorno Gerado', 'Espelho Gerado' ou
'Cancelamento Gerado') e a preservação do status anterior ao regenerar (ao
invés de sempre travar em "Retorno Gerado", o que fazia o pedido "regredir"
quando já tinha avançado pra Espelho ou Cancelamento).

Usa a mesma infra de OL_TEST/api/ (SQLite em memória via `sessao_teste` e
`criar_pedido_e_industria`), mas mocka as funções de infraestrutura
específicas de retorno (_build_industria, _build_pedido, verifica_pedido,
gerar_retorno_closeup, atualizar_status_pedido) pra isolar só a lógica de
gate/transição de status que este arquivo testa.
"""
from types import SimpleNamespace

import pytest

from app.services import operacoes
from app.services.operacoes import geracao
from ol_core.layouts import closeup as layout_closeup  # a geração passa pelo layout registrado
from ol_core.models.enums.tipo_layout import TipoLayout
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from .conftest import criar_pedido_e_industria


def _stub_infra(monkeypatch, gerar_retorno_ok=True, gerar_retorno_erro=None):
    monkeypatch.setattr(geracao, "_build_industria", lambda industria_db: SimpleNamespace(tipo_layout=TipoLayout.CLOSEUP))
    monkeypatch.setattr(geracao, "_build_pedido", lambda pedido_db: SimpleNamespace())
    monkeypatch.setattr(
        geracao,
        "verifica_pedido",
        lambda numero_pedido_ol: [SimpleNamespace(
            codigo_interno_pedido=1, cod_situacao="0", situacao="OK",
            data_cancelamento=None, quem_cancelou=None, data_faturamento=None,
        )],
    )
    if gerar_retorno_erro is not None:
        def _levanta(*a, **kw):
            raise gerar_retorno_erro
        monkeypatch.setattr(layout_closeup, "gerar_retorno_closeup", _levanta)
    else:
        monkeypatch.setattr(layout_closeup, "gerar_retorno_closeup", lambda *a, **kw: gerar_retorno_ok)

    status_chamados: list[str] = []

    def _fake_atualizar_status(numero_pedido_ol, status):
        status_chamados.append(status)

    monkeypatch.setattr(geracao, "atualizar_status_pedido", _fake_atualizar_status)
    monkeypatch.setattr(geracao, "exigir_cnpj_distribuidor", lambda: "11222333000181")
    monkeypatch.setattr(
        geracao, "reservar_status_pedido",
        lambda numero_pedido_ol, status, status_esperado=None: _fake_atualizar_status(numero_pedido_ol, status) or True,
    )
    return status_chamados


@pytest.mark.parametrize("status_inicial", ["Importado", "Verificar", "Pronto", "Falha"])
def test_gerar_retorno_com_status_nao_permitido_levanta_value_error(sessao_teste, monkeypatch, status_inicial):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=status_inicial)
    status_chamados = _stub_infra(monkeypatch)

    with pytest.raises(ValueError):
        operacoes.executar_gerar_retorno(pedido, id_usuario=1)

    assert status_chamados == []  # nunca chega a mexer no status


@pytest.mark.parametrize("status_inicial", [
    TipoStatusOper.RETORNO.value,      # "Retorno Gerado"
    TipoStatusOper.ESPELHO.value,      # "Espelho Gerado"
    TipoStatusOper.CANCELADO.value,    # "Cancelamento Gerado"
])
def test_gerar_retorno_com_sucesso_preserva_o_status_anterior(sessao_teste, monkeypatch, status_inicial):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=status_inicial)
    status_chamados = _stub_infra(monkeypatch, gerar_retorno_ok=True)

    resultado = operacoes.executar_gerar_retorno(pedido, id_usuario=1)

    assert resultado["sucesso"] is True
    # Passa por "Retorno Sendo Gerado" e volta pro status de ANTES — não
    # trava em "Retorno Gerado" quando o pedido já tinha avançado.
    assert status_chamados == [TipoStatusOper.GERANDO_RETORNO.value, status_inicial]


@pytest.mark.parametrize("status_inicial", [
    TipoStatusOper.RETORNO.value,
    TipoStatusOper.ESPELHO.value,
    TipoStatusOper.CANCELADO.value,
])
def test_gerar_retorno_com_falha_reverte_para_o_status_anterior(sessao_teste, monkeypatch, status_inicial):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=status_inicial)
    status_chamados = _stub_infra(monkeypatch, gerar_retorno_erro=RuntimeError("falha simulada no gerador"))

    with pytest.raises(RuntimeError):
        operacoes.executar_gerar_retorno(pedido, id_usuario=1)

    # Mesmo com erro, reverte pro status de ANTES (não hardcoded "Retorno Gerado").
    assert status_chamados == [TipoStatusOper.GERANDO_RETORNO.value, status_inicial]


# ---------------------------------------------------------------------------
# Nova tentativa manual após falha ("Falha no Retorno") e trava "Sendo Gerado"
# ---------------------------------------------------------------------------

def test_gerar_retorno_apos_falha_com_sucesso_vai_para_retorno_gerado(sessao_teste, monkeypatch):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=TipoStatusOper.FALHA_RETORNO.value)
    status_chamados = _stub_infra(monkeypatch, gerar_retorno_ok=True)

    resultado = operacoes.executar_gerar_retorno(pedido, id_usuario=1)

    assert resultado["sucesso"] is True
    # Não "restaura" a falha: o sucesso leva o pedido para "Retorno Gerado".
    assert status_chamados == [TipoStatusOper.GERANDO_RETORNO.value, TipoStatusOper.RETORNO.value]


def test_gerar_retorno_apos_falha_que_falha_de_novo_continua_em_falha(sessao_teste, monkeypatch):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=TipoStatusOper.FALHA_RETORNO.value)
    status_chamados = _stub_infra(monkeypatch, gerar_retorno_erro=RuntimeError("falha simulada"))

    with pytest.raises(RuntimeError):
        operacoes.executar_gerar_retorno(pedido, id_usuario=1)

    assert status_chamados == [TipoStatusOper.GERANDO_RETORNO.value, TipoStatusOper.FALHA_RETORNO.value]


@pytest.mark.parametrize("status_gerando", [
    TipoStatusOper.GERANDO_RETORNO.value,
    TipoStatusOper.GERANDO_ESPELHO.value,
    TipoStatusOper.GERANDO_CANCELAMENTO.value,
])
def test_gerar_retorno_bloqueado_enquanto_alguma_geracao_em_curso(sessao_teste, monkeypatch, status_gerando):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=status_gerando)
    status_chamados = _stub_infra(monkeypatch)

    with pytest.raises(ValueError, match="Aguarde"):
        operacoes.executar_gerar_retorno(pedido, id_usuario=1)

    assert status_chamados == []


def test_gerar_retorno_nao_gera_se_perder_a_corrida_pelo_status(monkeypatch):
    """B7: o gate valida o status lido, mas o serviço automático muda o status
    antes da reserva. O UPDATE condicional não grava (False) e a geração
    manual não começa — nem gera o arquivo, nem mexe no status."""
    # Objeto simples (sem banco): o fluxo só lê estes atributos antes da reserva.
    pedido = SimpleNamespace(
        numero_pedido_ol="00000000000000000001",
        status_operacional=TipoStatusOper.RETORNO.value,
        industria=SimpleNamespace(),
    )
    status_chamados = _stub_infra(monkeypatch)
    gerados = []
    monkeypatch.setattr(layout_closeup, "gerar_retorno_closeup", lambda *a, **kw: gerados.append(1) or True)
    reservas = []

    def _reserva_perdida(numero_pedido_ol, status, status_esperado=None):
        reservas.append((status, status_esperado))
        return False

    monkeypatch.setattr(geracao, "reservar_status_pedido", _reserva_perdida)

    with pytest.raises(ValueError, match="mudou"):
        operacoes.executar_gerar_retorno(pedido, id_usuario=1)

    assert reservas == [(TipoStatusOper.GERANDO_RETORNO.value, TipoStatusOper.RETORNO.value)]
    assert gerados == []
    assert status_chamados == []
