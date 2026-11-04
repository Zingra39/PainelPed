"""Parâmetro BLOQUEAR_ENVIO_PEDIDO_VERIFICAR (tela de Parametrização).

Ligado ("1"), a transmissão MANUAL — individual (POST /pedidos/{id}/transmitir) e
em lote (POST /pedidos/lote/transmitir + preview) — só aceita pedidos com
status_operacional "Pronto". Pedido em "Verificar" (ou qualquer outro status)
fica barrado até a ocorrência ser resolvida e o pedido reprocessado.

Desligado ou ausente = comportamento anterior, sem nenhuma restrição nova.
O servidor aplica a regra (a tela só a reflete); o flag `envio_somente_pronto`
vai nas respostas de /confeccao e do detalhe porque o Operador Logístico, quem
transmite, não lê GET /parametros.

Mesma infra de test_pedido_analise.py: SQLite em memória, `executar_transmitir`
mockado (nenhum teste copia arquivo de verdade).
"""
from datetime import datetime

import pytest

from app.models import Parametro, Pedido
from app.routers import pedidos
from app.routers.pedidos._comum import _marcar_transmitindo
from app.routers.pedidos.lote import _transmitir_pedido
from app.services import operacoes
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from .conftest import criar_pedido_e_industria

CHAVE = "BLOQUEAR_ENVIO_PEDIDO_VERIFICAR"
NAO_TRANSMITIDO = "Não Transmitido"
PRONTO = TipoStatusOper.PRONTO.value
VERIFICAR = TipoStatusOper.VERIFICAR.value


def _parametro(sessao_teste, valor: str) -> None:
    sessao_teste.add(Parametro(chave=CHAVE, valor=valor, descricao="teste"))
    sessao_teste.commit()


def _pedido(sessao_teste, status: str, numero: str = "00000000000000000001", base: Pedido | None = None) -> Pedido:
    """Pedido na triagem. O 2º em diante reaproveita a indústria do primeiro
    (criar_pedido_e_industria cria uma nova a cada chamada e o CNPJ é UNIQUE)."""
    if base is None:
        return criar_pedido_e_industria(
            sessao_teste, numero_pedido_ol=numero, status_erp=NAO_TRANSMITIDO, status_operacional=status
        )
    pedido = Pedido(
        numero_pedido_ol=numero,
        id_industria=base.id_industria,
        nome_arquivo=f"PEDIDO_{numero}.txt",
        cnpj_cliente="12345678000199",
        status_erp=NAO_TRANSMITIDO,
        status_operacional=status,
        criado_em=datetime.now(),
        atualizado_em=datetime.now(),
    )
    sessao_teste.add(pedido)
    sessao_teste.commit()
    sessao_teste.refresh(pedido)
    return pedido


def _recarregar(sessao_teste, pedido: Pedido) -> Pedido:
    sessao_teste.expire_all()
    return sessao_teste.query(Pedido).filter_by(id=pedido.id).first()


@pytest.fixture()
def transmitidos(monkeypatch) -> list[str]:
    """Registra o que o backend tentou transmitir (em vez de copiar arquivo)."""
    lista: list[str] = []

    def _fn(pedido_db, id_usuario):
        lista.append(pedido_db.numero_pedido_ol)
        return {"sucesso": True, "mensagem": "ok"}

    monkeypatch.setattr(operacoes, "executar_transmitir", _fn)
    return lista


@pytest.fixture()
def operador(montar_client):
    return montar_client(pedidos.router, nome_perfil="Operador Logístico")


# ------------------------------------------------------------- individual

def test_individual_com_parametro_ligado_barra_pedido_verificar(sessao_teste, operador, transmitidos):
    _parametro(sessao_teste, "1")
    pedido = _pedido(sessao_teste, VERIFICAR)

    resposta = operador.post(f"/pedidos/{pedido.id}/transmitir")

    assert resposta.status_code == 422
    assert "Pronto" in resposta.json()["detail"]
    assert "Verificar" in resposta.json()["detail"]
    assert transmitidos == []                                   # nada foi copiado
    atual = _recarregar(sessao_teste, pedido)
    assert atual.status_operacional == VERIFICAR                # status intacto (não virou Falha/Transmitindo)
    assert atual.status_erp == NAO_TRANSMITIDO


def test_individual_com_parametro_ligado_aceita_pedido_pronto(sessao_teste, operador, transmitidos):
    _parametro(sessao_teste, "1")
    pedido = _pedido(sessao_teste, PRONTO)

    resposta = operador.post(f"/pedidos/{pedido.id}/transmitir")

    assert resposta.status_code == 200
    assert transmitidos == [pedido.numero_pedido_ol]
    assert _recarregar(sessao_teste, pedido).status_operacional == TipoStatusOper.TRANSMITIDO.value


@pytest.mark.parametrize("status", ["Importado", TipoStatusOper.FALHA.value, TipoStatusOper.REPROCESSANDO.value])
def test_individual_com_parametro_ligado_so_pronto_passa_qualquer_outro_status_e_barrado(
    sessao_teste, operador, transmitidos, status
):
    _parametro(sessao_teste, "1")
    pedido = _pedido(sessao_teste, status)

    assert operador.post(f"/pedidos/{pedido.id}/transmitir").status_code == 422
    assert transmitidos == []


def test_individual_com_parametro_ligado_pedido_em_analise_continua_com_a_mensagem_de_analise(
    sessao_teste, operador, transmitidos
):
    _parametro(sessao_teste, "1")
    pedido = _pedido(sessao_teste, TipoStatusOper.EM_ANALISE.value)

    resposta = operador.post(f"/pedidos/{pedido.id}/transmitir")

    assert resposta.status_code == 422
    assert "em análise" in resposta.json()["detail"]
    assert transmitidos == []


@pytest.mark.parametrize("valor", ["0", "", None])
def test_individual_com_parametro_desligado_mantem_o_comportamento_antigo(sessao_teste, operador, transmitidos, valor):
    if valor is not None:
        _parametro(sessao_teste, valor)
    pedido = _pedido(sessao_teste, VERIFICAR)

    assert operador.post(f"/pedidos/{pedido.id}/transmitir").status_code == 200
    assert transmitidos == [pedido.numero_pedido_ol]


def test_individual_sem_a_linha_do_parametro_no_banco_nao_bloqueia(sessao_teste, operador, transmitidos):
    # Ambiente em que o INSERT ainda não rodou: nada muda até a chave existir.
    pedido = _pedido(sessao_teste, VERIFICAR)

    assert operador.post(f"/pedidos/{pedido.id}/transmitir").status_code == 200


# ------------------------------------------------------------- lote

def _tres_pedidos(sessao_teste):
    pronto = _pedido(sessao_teste, PRONTO, "00000000000000000001")
    _pedido(sessao_teste, VERIFICAR, "00000000000000000002", base=pronto)
    _pedido(sessao_teste, "Importado", "00000000000000000003", base=pronto)
    return pronto


def test_lote_com_parametro_ligado_transmite_so_pedidos_prontos(sessao_teste, operador, transmitidos):
    _parametro(sessao_teste, "1")
    _tres_pedidos(sessao_teste)

    resposta = operador.post("/pedidos/lote/transmitir", json={"apenas_sem_ocorrencia": False})

    assert resposta.status_code == 200
    assert resposta.json()["total"] == 1
    assert transmitidos == ["00000000000000000001"]


def test_preview_do_lote_bate_com_o_envio_quando_o_parametro_esta_ligado(sessao_teste, operador, transmitidos):
    _parametro(sessao_teste, "1")
    _tres_pedidos(sessao_teste)

    preview = operador.get("/pedidos/lote/transmitir/preview", params={"apenas_sem_ocorrencia": "false"}).json()
    envio = operador.post("/pedidos/lote/transmitir", json={"apenas_sem_ocorrencia": False}).json()

    assert preview["total"] == 1
    assert envio["total"] == preview["total"]


def test_lote_com_parametro_desligado_continua_incluindo_todos(sessao_teste, operador, transmitidos):
    _parametro(sessao_teste, "0")
    _tres_pedidos(sessao_teste)

    resposta = operador.post("/pedidos/lote/transmitir", json={"apenas_sem_ocorrencia": False})

    assert resposta.json()["total"] == 3
    assert sorted(transmitidos) == ["00000000000000000001", "00000000000000000002", "00000000000000000003"]


def test_marcar_transmitindo_recusa_pedido_que_saiu_de_pronto_depois_da_lista_montada(sessao_teste):
    # No lote, o pedido pode voltar para "Verificar" (reprocessamento) entre a
    # montagem da lista e a vez dele no loop — o UPDATE condicional é a trava.
    pedido = _pedido(sessao_teste, VERIFICAR)

    assert _marcar_transmitindo(pedido, sessao_teste, somente_pronto=True) is False
    assert _recarregar(sessao_teste, pedido).status_operacional == VERIFICAR


def test_marcar_transmitindo_sem_restricao_continua_aceitando_verificar(sessao_teste):
    pedido = _pedido(sessao_teste, VERIFICAR)

    assert _marcar_transmitindo(pedido, sessao_teste) is True
    assert _recarregar(sessao_teste, pedido).status_operacional == TipoStatusOper.TRANSMITINDO.value


def test_item_do_lote_barrado_pelo_parametro_informa_o_motivo(sessao_teste):
    pedido = _pedido(sessao_teste, VERIFICAR)

    item = _transmitir_pedido(pedido, sessao_teste, usuario_id=1, somente_pronto=True)

    assert item.sucesso is False
    assert "parametrização" in item.mensagem


# ------------------------------------------------------------- flag nas respostas

@pytest.mark.parametrize("perfil", ["Operador Logístico", "Gerente Comercial", "Administrador"])
def test_confeccao_expoe_o_flag_para_qualquer_perfil(sessao_teste, montar_client, perfil):
    _parametro(sessao_teste, "1")
    _pedido(sessao_teste, PRONTO)

    corpo = montar_client(pedidos.router, nome_perfil=perfil).get("/pedidos/confeccao").json()

    assert corpo["envio_somente_pronto"] is True


def test_confeccao_expoe_flag_falso_com_parametro_desligado_ou_ausente(sessao_teste, operador):
    _pedido(sessao_teste, PRONTO)
    assert operador.get("/pedidos/confeccao").json()["envio_somente_pronto"] is False

    _parametro(sessao_teste, "0")
    assert operador.get("/pedidos/confeccao").json()["envio_somente_pronto"] is False


def test_detalhe_do_pedido_expoe_o_flag(sessao_teste, operador):
    _parametro(sessao_teste, "1")
    pedido = _pedido(sessao_teste, VERIFICAR)

    assert operador.get(f"/pedidos/{pedido.id}").json()["envio_somente_pronto"] is True
    assert operador.get(f"/pedidos/{pedido.id}/detalhes").json()["envio_somente_pronto"] is True
