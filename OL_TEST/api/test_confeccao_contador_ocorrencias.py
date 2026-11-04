"""Contador de ocorrências da Triagem (GET /pedidos/confeccao e /confeccao/export).

Ocorrência com severidade "IGNORADO" (parâmetro de ignorar ligado na tela de
Parametrização — TipoSeveridade.IGNORADO) não é pendência: não entra no número
da coluna "Ocorr." da Triagem nem na coluna "Ocorrências Abertas" da planilha.

Travado aqui, de propósito, mesmo para ocorrência IGNORADO com resolvido=False:
é exatamente o que o INSERT de `registrar_ocorrencia` grava hoje (ele fixa
resolvido=0 e não repassa `erro.resolvido`), então o contador não pode depender
do flag `resolvido` para esconder as ignoradas.
"""
import io
from datetime import datetime

import pandas as pd

from app.models import Pedido, PedidoOcorrencia
from app.routers import pedidos
from ol_core.models.enums.tipo_severidade import TipoSeveridade
from .conftest import criar_pedido_e_industria

NAO_TRANSMITIDO = "Não Transmitido"
IGNORADO = TipoSeveridade.IGNORADO.value


def _ocorrencia(sessao_teste, pedido: Pedido, severidade, resolvido: bool = False) -> None:
    sessao_teste.add(PedidoOcorrencia(
        numero_pedido_ol=pedido.numero_pedido_ol,
        severidade=severidade,
        codigo="0",
        descricao="teste",
        resolvido=resolvido,
        criado_em=datetime.now(),
    ))
    sessao_teste.commit()


def _pedido(sessao_teste) -> Pedido:
    return criar_pedido_e_industria(sessao_teste, status_erp=NAO_TRANSMITIDO)


def _abertas_na_tela(client) -> int:
    return client.get("/pedidos/confeccao").json()["items"][0]["total_ocorrencias_abertas"]


def test_contador_nao_conta_ocorrencia_ignorada(sessao_teste, montar_client):
    pedido = _pedido(sessao_teste)
    _ocorrencia(sessao_teste, pedido, TipoSeveridade.ERRO.value)
    _ocorrencia(sessao_teste, pedido, TipoSeveridade.ALERTA.value)
    _ocorrencia(sessao_teste, pedido, IGNORADO)            # resolvido=False, como o INSERT atual grava
    _ocorrencia(sessao_teste, pedido, IGNORADO)
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    item = client.get("/pedidos/confeccao").json()["items"][0]

    assert item["total_ocorrencias_abertas"] == 2          # ERRO + ALERTA
    assert item["total_ocorrencias"] == 4                  # o total geral não muda


def test_pedido_so_com_ocorrencias_ignoradas_mostra_zero(sessao_teste, montar_client):
    pedido = _pedido(sessao_teste)
    _ocorrencia(sessao_teste, pedido, IGNORADO)
    _ocorrencia(sessao_teste, pedido, IGNORADO, resolvido=True)
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    assert _abertas_na_tela(client) == 0


def test_contador_continua_contando_ocorrencia_sem_severidade(sessao_teste, montar_client):
    # Em SQL `severidade != 'IGNORADO'` descarta os NULL: sem tratamento
    # explícito, uma ocorrência sem classificação sumiria do contador.
    pedido = _pedido(sessao_teste)
    _ocorrencia(sessao_teste, pedido, None)
    _ocorrencia(sessao_teste, pedido, IGNORADO)
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    assert _abertas_na_tela(client) == 1


def test_contador_continua_ignorando_ocorrencia_resolvida(sessao_teste, montar_client):
    pedido = _pedido(sessao_teste)
    _ocorrencia(sessao_teste, pedido, TipoSeveridade.ERRO.value, resolvido=True)
    _ocorrencia(sessao_teste, pedido, TipoSeveridade.ERRO.value)
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    assert _abertas_na_tela(client) == 1


def test_planilha_da_triagem_bate_com_o_contador_da_tela(sessao_teste, montar_client):
    pedido = _pedido(sessao_teste)
    _ocorrencia(sessao_teste, pedido, TipoSeveridade.CRITICO.value)
    _ocorrencia(sessao_teste, pedido, IGNORADO)
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    resposta = client.get("/pedidos/confeccao/export")

    assert resposta.status_code == 200
    planilha = pd.read_excel(io.BytesIO(resposta.content))
    assert planilha.loc[0, "Ocorrências Abertas"] == 1
    assert planilha.loc[0, "Ocorrências Abertas"] == _abertas_na_tela(client)
