"""Testes de app.routers.pedidos.detalhe._deduplicar_ocorrencias e dos endpoints de
detalhe do pedido (/pedidos/{id}/detalhes e /pedidos/{id}).

Cenário relatado pelo usuário: reprocessamentos sucessivos podem detectar o
MESMO problema mais de uma vez — cada detecção grava uma linha nova em
pedido_ocorrencia (correto pro histórico), mas a tela de detalhes exibia
TODAS as linhas, inclusive repetidas com o mesmo texto de descrição. Só a
linha mais recente de cada mensagem deve aparecer na tela.
"""
from datetime import datetime, timedelta

import pytest

from app.models import Pedido, PedidoItem, PedidoItemOcorrencia, PedidoOcorrencia
from app.routers.pedidos import router as pedidos_router
from app.routers.pedidos.detalhe import _deduplicar_ocorrencias
from app.services import operacoes
from .conftest import criar_pedido_e_industria


class _OcorrenciaFake:
    """Objeto simples com os únicos atributos que _deduplicar_ocorrencias usa
    — evita depender de sessão/banco só para testar a função pura."""
    def __init__(self, descricao, criado_em):
        self.descricao = descricao
        self.criado_em = criado_em


def test_deduplicar_ocorrencias_mantem_so_a_mais_recente_por_descricao():
    agora = datetime.now()
    resolvida_antiga = _OcorrenciaFake("Desconto maior que o configurado", agora - timedelta(days=2))
    aberta_recente = _OcorrenciaFake("Desconto maior que o configurado", agora)
    unica = _OcorrenciaFake("Condição expirada", agora - timedelta(days=2))

    resultado = _deduplicar_ocorrencias([resolvida_antiga, unica, aberta_recente])

    assert resultado == [unica, aberta_recente]
    assert resolvida_antiga not in resultado


def test_deduplicar_ocorrencias_sem_duplicatas_devolve_tudo_igual():
    agora = datetime.now()
    a = _OcorrenciaFake("Mensagem A", agora)
    b = _OcorrenciaFake("Mensagem B", agora)

    resultado = _deduplicar_ocorrencias([a, b])

    assert resultado == [a, b]


def test_deduplicar_ocorrencias_lista_vazia_devolve_vazia():
    assert _deduplicar_ocorrencias([]) == []


# ===================================================================
# Endpoints de detalhe — cenário exato relatado: 4 ocorrências gravadas,
# 2 delas com a mesma descrição (uma resolvida antiga, uma aberta recente)
# → só 3 devem aparecer na resposta.
# ===================================================================

def _gravar_ocorrencias_do_cenario_relatado(sessao_teste, pedido):
    agora = datetime.now()
    linhas = [
        PedidoOcorrencia(
            numero_pedido_ol=pedido.numero_pedido_ol,
            severidade="ALERTA", codigo="0",
            descricao="Condição 1.S G-ANLODIPINO 5MG 30CPR N.Q está expirada: 2026082100325423397P",
            resolvido=True, criado_em=agora - timedelta(days=2),
        ),
        PedidoOcorrencia(
            numero_pedido_ol=pedido.numero_pedido_ol,
            severidade="ALERTA", codigo="0",
            descricao="Desconto do G-ANLODIPINO 5MG 30CPR N.QUIMICA - 7896714211305 maior que o configurado na condicao",
            resolvido=True, criado_em=agora - timedelta(days=2),
        ),
        PedidoOcorrencia(
            numero_pedido_ol=pedido.numero_pedido_ol,
            severidade="ALERTA", codigo="0",
            descricao="Minimo da condição não configurado ou não encontrado para a condição 0",
            resolvido=False, criado_em=agora,
        ),
        PedidoOcorrencia(
            numero_pedido_ol=pedido.numero_pedido_ol,
            severidade="ALERTA", codigo="0",
            descricao="Desconto do G-ANLODIPINO 5MG 30CPR N.QUIMICA - 7896714211305 maior que o configurado na condicao",
            resolvido=False, criado_em=agora,
        ),
    ]
    for linha in linhas:
        sessao_teste.add(linha)
    sessao_teste.commit()


def test_endpoint_detalhes_completo_nao_exibe_ocorrencias_duplicadas(sessao_teste, montar_client, monkeypatch):
    monkeypatch.setattr(operacoes, "buscar_titulo_erp", lambda nome_arquivo: None)

    pedido = criar_pedido_e_industria(sessao_teste)
    _gravar_ocorrencias_do_cenario_relatado(sessao_teste, pedido)

    client = montar_client(pedidos_router, nome_perfil="Operador Logístico")

    resposta = client.get(f"/pedidos/{pedido.id}/detalhes")

    assert resposta.status_code == 200
    ocorrencias = resposta.json()["ocorrencias"]
    assert len(ocorrencias) == 3
    descricoes = [o["descricao"] for o in ocorrencias]
    assert len(descricoes) == len(set(descricoes))  # nenhuma descrição repetida
    # a ocorrência de desconto que sobra é a mais recente (aberta), não a antiga (resolvida)
    desconto = next(o for o in ocorrencias if o["descricao"].startswith("Desconto do G-ANLODIPINO"))
    assert desconto["resolvido"] is False


def test_endpoint_detalhe_simples_nao_exibe_ocorrencias_duplicadas(sessao_teste, montar_client, monkeypatch):
    pedido = criar_pedido_e_industria(sessao_teste)
    _gravar_ocorrencias_do_cenario_relatado(sessao_teste, pedido)

    client = montar_client(pedidos_router, nome_perfil="Operador Logístico")

    resposta = client.get(f"/pedidos/{pedido.id}")

    assert resposta.status_code == 200
    ocorrencias = resposta.json()["ocorrencias"]
    assert len(ocorrencias) == 3


def test_endpoint_detalhes_completo_dedup_tambem_vale_para_ocorrencias_de_item(sessao_teste, montar_client, monkeypatch):
    monkeypatch.setattr(operacoes, "buscar_titulo_erp", lambda nome_arquivo: None)

    pedido = criar_pedido_e_industria(sessao_teste)
    item = PedidoItem(
        numero_pedido_ol=pedido.numero_pedido_ol,
        ean="7896714211305", codigo_produto_erp=41637,
        quantidade_solicitada=60, quantidade_atendida=0,
        preco=33.48, desconto=96.15, cod_motivo=0, status="Verificar", id_cond=8736,
    )
    sessao_teste.add(item)
    sessao_teste.commit()
    sessao_teste.refresh(item)

    agora = datetime.now()
    sessao_teste.add_all([
        PedidoItemOcorrencia(
            id_pedido_item=item.id, severidade="0", codigo="0",
            descricao="Desconto acima do limite", resolvido=True, criado_em=agora - timedelta(days=2),
        ),
        PedidoItemOcorrencia(
            id_pedido_item=item.id, severidade="0", codigo="0",
            descricao="Desconto acima do limite", resolvido=False, criado_em=agora,
        ),
    ])
    sessao_teste.commit()

    client = montar_client(pedidos_router, nome_perfil="Operador Logístico")

    resposta = client.get(f"/pedidos/{pedido.id}/detalhes")

    assert resposta.status_code == 200
    itens = resposta.json()["itens"]
    assert len(itens) == 1
    assert len(itens[0]["ocorrencias"]) == 1
    assert itens[0]["ocorrencias"][0]["resolvido"] is False
