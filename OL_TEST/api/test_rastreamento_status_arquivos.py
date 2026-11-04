"""
Testes de app.routers.pedidos._rastreamento._montar_status_arquivos e
app.services.operacoes.mapear_status_arquivo — a lógica que alimenta as
colunas Retorno/Espelho/Cancelamento da tela de Rastreamento.

Cobre especificamente o cenário perguntado pelo usuário: quando o Espelho é
gerado (o que só acontece depois do Retorno), as colunas de Retorno E
Espelho devem aparecer preenchidas ao mesmo tempo — cada uma vem da sua
própria linha na tabela `arquivo` (tipo="retorno"/"espelho"/"cancelado"),
independente do status_operacional atual do pedido. Também cobre os novos
valores "Falha no X", que substituíram o "Falha" genérico nos três
services de geração.
"""
from datetime import datetime, timedelta

import pytest

from app.models import Arquivo
from app.routers import pedidos as pedidos_router
from app.routers.pedidos._rastreamento import _filtrar_historico, _filtrar_rastreamento, _montar_status_arquivos
from app.services.operacoes import mapear_status_arquivo
from ol_core.models.enums.tipo_arquivo import TipoArquivo
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from .conftest import criar_pedido_e_industria


def _add_arquivo(sessao_teste, pedido, tipo, situacao, criado_em=None):
    arquivo = Arquivo(
        numero_pedido_ol=pedido.numero_pedido_ol,
        nome=f"{tipo.upper()}_{pedido.numero_pedido_ol}.TXT",
        tipo=tipo,
        hash_md5="",
        caminho="/fake/caminho",
        situacao=situacao,
        criado_em=criado_em or datetime.now(),
    )
    sessao_teste.add(arquivo)
    sessao_teste.commit()
    sessao_teste.refresh(pedido)
    return arquivo


# ===================================================================
# mapear_status_arquivo — reconhece os valores gravados pelos services
# ===================================================================

@pytest.mark.parametrize("tipo, situacao, esperado", [
    (TipoArquivo.RETORNO.value, TipoStatusOper.GERANDO_RETORNO.value, TipoStatusOper.GERANDO_RETORNO.value),
    (TipoArquivo.RETORNO.value, TipoStatusOper.RETORNO.value, TipoStatusOper.RETORNO.value),
    (TipoArquivo.RETORNO.value, TipoStatusOper.FALHA_RETORNO.value, TipoStatusOper.FALHA_RETORNO.value),
    (TipoArquivo.ESPELHO.value, TipoStatusOper.GERANDO_ESPELHO.value, TipoStatusOper.GERANDO_ESPELHO.value),
    (TipoArquivo.ESPELHO.value, TipoStatusOper.ESPELHO.value, TipoStatusOper.ESPELHO.value),
    (TipoArquivo.ESPELHO.value, TipoStatusOper.FALHA_ESPELHO.value, TipoStatusOper.FALHA_ESPELHO.value),
    (TipoArquivo.CANCELADO.value, TipoStatusOper.GERANDO_CANCELAMENTO.value, TipoStatusOper.GERANDO_CANCELAMENTO.value),
    (TipoArquivo.CANCELADO.value, TipoStatusOper.CANCELADO.value, TipoStatusOper.CANCELADO.value),
    (TipoArquivo.CANCELADO.value, TipoStatusOper.FALHA_CANCELAMENTO.value, TipoStatusOper.FALHA_CANCELAMENTO.value),
])
def test_mapear_status_arquivo_reconhece_os_valores_gravados_pelos_services(tipo, situacao, esperado):
    assert mapear_status_arquivo(tipo, situacao) == esperado


@pytest.mark.parametrize("tipo, situacao, esperado", [
    # Fallback pra dados legados (situacao gravada antes desses valores baterem 1:1)
    (TipoArquivo.RETORNO.value, "gerado", "Retorno Gerado"),
    (TipoArquivo.ESPELHO.value, "Enviado", "Espelho Enviado"),
    (TipoArquivo.CANCELADO.value, "erro", TipoStatusOper.FALHA.value),
    (TipoArquivo.RETORNO.value, "em criação", "Gerando Retorno"),
])
def test_mapear_status_arquivo_fallback_legado(tipo, situacao, esperado):
    assert mapear_status_arquivo(tipo, situacao) == esperado


def test_mapear_status_arquivo_tipo_desconhecido_devolve_none():
    assert mapear_status_arquivo("nao-existe", TipoStatusOper.RETORNO.value) is None


# ===================================================================
# _montar_status_arquivos — badges simultâneos por etapa
# ===================================================================

def test_com_retorno_e_espelho_gerados_as_duas_colunas_aparecem_ao_mesmo_tempo(sessao_teste):
    # Pergunta original do usuário: ao gerar o Espelho (que só acontece depois
    # do Retorno), a coluna de Retorno continua mostrando "Retorno Gerado" —
    # cada arquivo tem sua própria linha/situação na tabela `arquivo`, então
    # gerar o Espelho não apaga o que já foi mostrado pro Retorno.
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=TipoStatusOper.ESPELHO.value)
    _add_arquivo(sessao_teste, pedido, TipoArquivo.RETORNO.value, TipoStatusOper.RETORNO.value,
                 criado_em=datetime.now() - timedelta(minutes=5))
    _add_arquivo(sessao_teste, pedido, TipoArquivo.ESPELHO.value, TipoStatusOper.ESPELHO.value)

    retorno_status, espelho_status, cancelamento_status, falha_geral = _montar_status_arquivos(pedido)

    assert retorno_status == TipoStatusOper.RETORNO.value
    assert espelho_status == TipoStatusOper.ESPELHO.value
    assert cancelamento_status is None
    assert falha_geral is False


def test_so_com_retorno_gerado_apenas_a_coluna_de_retorno_aparece(sessao_teste):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=TipoStatusOper.RETORNO.value)
    _add_arquivo(sessao_teste, pedido, TipoArquivo.RETORNO.value, TipoStatusOper.RETORNO.value)

    retorno_status, espelho_status, cancelamento_status, falha_geral = _montar_status_arquivos(pedido)

    assert retorno_status == TipoStatusOper.RETORNO.value
    assert espelho_status is None
    assert cancelamento_status is None
    assert falha_geral is False


def test_pega_a_situacao_mais_recente_quando_ha_mais_de_um_arquivo_do_mesmo_tipo(sessao_teste):
    # Regeneração manual do retorno: a linha antiga (Falha) é substituída em
    # situação pela mais nova (Retorno Gerado) — _montar_status_arquivos usa
    # o arquivo mais recente por tipo.
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=TipoStatusOper.RETORNO.value)
    _add_arquivo(sessao_teste, pedido, TipoArquivo.RETORNO.value, TipoStatusOper.FALHA_RETORNO.value,
                 criado_em=datetime.now() - timedelta(minutes=10))
    _add_arquivo(sessao_teste, pedido, TipoArquivo.RETORNO.value, TipoStatusOper.RETORNO.value,
                 criado_em=datetime.now())

    retorno_status, _, _, falha_geral = _montar_status_arquivos(pedido)

    assert retorno_status == TipoStatusOper.RETORNO.value
    assert falha_geral is False


def test_falha_no_retorno_aparece_na_coluna_de_retorno_sem_acionar_o_triangulo_geral(sessao_teste):
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=TipoStatusOper.FALHA_RETORNO.value)
    _add_arquivo(sessao_teste, pedido, TipoArquivo.RETORNO.value, TipoStatusOper.FALHA_RETORNO.value)

    retorno_status, espelho_status, cancelamento_status, falha_geral = _montar_status_arquivos(pedido)

    assert retorno_status == TipoStatusOper.FALHA_RETORNO.value
    # A falha já está refletida na coluna — não precisa do triângulo geral também.
    assert falha_geral is False


def test_falha_sem_nenhuma_linha_de_arquivo_aciona_o_triangulo_geral(sessao_teste):
    # Ex.: falha bem no início da geração, antes de qualquer linha em `arquivo`
    # existir ainda — nenhuma coluna reflete a falha, então o triângulo cobre.
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=TipoStatusOper.FALHA_ESPELHO.value)

    retorno_status, espelho_status, cancelamento_status, falha_geral = _montar_status_arquivos(pedido)

    assert espelho_status is None
    assert falha_geral is True


def test_cancelamento_gerado_sem_linha_na_tabela_arquivo_usa_o_fallback_do_status_operacional(sessao_teste):
    # Fallback já existente: se por algum motivo não há linha tipo="cancelado"
    # na tabela arquivo mas o pedido já está com status "Cancelamento Gerado",
    # a coluna reflete isso mesmo assim.
    pedido = criar_pedido_e_industria(sessao_teste, status_operacional=TipoStatusOper.CANCELADO.value)

    _, _, cancelamento_status, _ = _montar_status_arquivos(pedido)

    assert cancelamento_status == TipoStatusOper.CANCELADO.value


# ===================================================================
# Card "usar status_erp de forma mais adequada": pedidos com o fluxo
# encerrado (Pedido Concluido / Pedido Cancelado) somem do Rastreamento
# e passam a aparecer só no Histórico — cobre a raiz do bug relatado pelo
# usuário (Historico.tsx buscava um teto fixo de 300 linhas e classificava
# "concluído" no cliente, então pedidos concluídos há mais tempo somem da
# lista conforme o volume de pedidos ativos cresce).
# ===================================================================

def _criar_industria_teste(sessao_teste, nome="Industria Teste", cnpj="12345678000199"):
    from app.models import Industria

    industria = Industria(nome=nome, cnpj=cnpj, ativo=True)
    sessao_teste.add(industria)
    sessao_teste.commit()
    sessao_teste.refresh(industria)
    return industria


def _criar_pedido_com_status_erp(sessao_teste, industria, numero_pedido_ol, status_erp, **extra):
    # NÃO usa criar_pedido_e_industria (ela cria uma Industria nova a cada
    # chamada com um CNPJ fixo — ótimo pra um pedido só por teste, mas viola
    # a constraint UNIQUE de cnpj quando o teste precisa de vários pedidos
    # associados à mesma indústria, como aqui).
    dados = dict(
        numero_pedido_ol=numero_pedido_ol,
        id_industria=industria.id,
        nome_arquivo=f"PEDIDO_{numero_pedido_ol}.txt",
        codigo_interno_erp=100,
        cnpj_cliente="12345678000199",
        status_operacional=TipoStatusOper.TRANSMITIDO.value,
        status_erp=status_erp,
        criado_em=datetime.now(),
        atualizado_em=datetime.now(),
    )
    dados.update(extra)
    from app.models import Pedido

    pedido = Pedido(**dados)
    sessao_teste.add(pedido)
    sessao_teste.commit()
    sessao_teste.refresh(pedido)
    return pedido


def test_filtrar_rastreamento_exclui_processo_concluido_e_pedido_cancelado(sessao_teste):
    industria = _criar_industria_teste(sessao_teste)
    transmitido = _criar_pedido_com_status_erp(sessao_teste, industria, "1", TipoStatusErp.TRANSMITIDO.value)
    aguardando = _criar_pedido_com_status_erp(sessao_teste, industria, "2", TipoStatusErp.AGUARDANDO_FATURAMENTO.value)
    concluido = _criar_pedido_com_status_erp(sessao_teste, industria, "3", TipoStatusErp.PROCESSO_CONCLUIDO.value)
    cancelado = _criar_pedido_com_status_erp(sessao_teste, industria, "4", TipoStatusErp.PEDIDO_CANCELADO.value)
    nao_transmitido = _criar_pedido_com_status_erp(sessao_teste, industria, "5", TipoStatusErp.NAO_TRANSMITIDO.value)

    resultado = _filtrar_rastreamento(sessao_teste, None, None, None, None)
    numeros = {p.numero_pedido_ol for p in resultado}

    assert numeros == {transmitido.numero_pedido_ol, aguardando.numero_pedido_ol}
    assert concluido.numero_pedido_ol not in numeros
    assert cancelado.numero_pedido_ol not in numeros
    assert nao_transmitido.numero_pedido_ol not in numeros


def test_filtrar_historico_inclui_apenas_processo_concluido_e_pedido_cancelado(sessao_teste):
    industria = _criar_industria_teste(sessao_teste)
    transmitido = _criar_pedido_com_status_erp(sessao_teste, industria, "1", TipoStatusErp.TRANSMITIDO.value)
    aguardando = _criar_pedido_com_status_erp(sessao_teste, industria, "2", TipoStatusErp.AGUARDANDO_FATURAMENTO.value)
    concluido = _criar_pedido_com_status_erp(sessao_teste, industria, "3", TipoStatusErp.PROCESSO_CONCLUIDO.value)
    cancelado = _criar_pedido_com_status_erp(sessao_teste, industria, "4", TipoStatusErp.PEDIDO_CANCELADO.value)

    resultado = _filtrar_historico(sessao_teste, None, None, None, None, None, None).all()
    numeros = {p.numero_pedido_ol for p in resultado}

    assert numeros == {concluido.numero_pedido_ol, cancelado.numero_pedido_ol}
    assert transmitido.numero_pedido_ol not in numeros
    assert aguardando.numero_pedido_ol not in numeros


def test_filtrar_historico_respeita_filtro_por_status_erp(sessao_teste):
    industria = _criar_industria_teste(sessao_teste)
    concluido = _criar_pedido_com_status_erp(sessao_teste, industria, "3", TipoStatusErp.PROCESSO_CONCLUIDO.value)
    cancelado = _criar_pedido_com_status_erp(sessao_teste, industria, "4", TipoStatusErp.PEDIDO_CANCELADO.value)

    resultado = _filtrar_historico(
        sessao_teste, None, None, None, TipoStatusErp.PEDIDO_CANCELADO.value, None, None
    ).all()
    numeros = {p.numero_pedido_ol for p in resultado}

    assert numeros == {cancelado.numero_pedido_ol}
    assert concluido.numero_pedido_ol not in numeros


def test_filtrar_historico_respeita_filtro_por_industria_nome(sessao_teste):
    industria = _criar_industria_teste(sessao_teste)
    outra_industria = _criar_industria_teste(sessao_teste, nome="Outra Industria", cnpj="99888777000166")

    concluido = _criar_pedido_com_status_erp(sessao_teste, industria, "3", TipoStatusErp.PROCESSO_CONCLUIDO.value)
    outro = _criar_pedido_com_status_erp(sessao_teste, outra_industria, "6", TipoStatusErp.PROCESSO_CONCLUIDO.value)

    resultado = _filtrar_historico(sessao_teste, None, None, "Outra Industria", None, None, None).all()
    numeros = {p.numero_pedido_ol for p in resultado}

    assert numeros == {outro.numero_pedido_ol}
    assert concluido.numero_pedido_ol not in numeros


def test_endpoint_historico_devolve_apenas_pedidos_concluidos_e_cancelados_com_paginacao(sessao_teste, montar_client):
    industria = _criar_industria_teste(sessao_teste)
    for i in range(3):
        _criar_pedido_com_status_erp(sessao_teste, industria, f"conc-{i}", TipoStatusErp.PROCESSO_CONCLUIDO.value)
    _criar_pedido_com_status_erp(sessao_teste, industria, "canc-0", TipoStatusErp.PEDIDO_CANCELADO.value)
    _criar_pedido_com_status_erp(sessao_teste, industria, "transm-0", TipoStatusErp.TRANSMITIDO.value)

    client = montar_client(pedidos_router.router, nome_perfil="Operador Logístico")

    resposta = client.get("/pedidos/historico", params={"page": 1, "size": 2})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 4
    assert corpo["pages"] == 2
    assert len(corpo["items"]) == 2

    resposta_pagina_2 = client.get("/pedidos/historico", params={"page": 2, "size": 2})
    assert len(resposta_pagina_2.json()["items"]) == 2

    numeros_retornados = {item["numero_pedido_ol"] for item in corpo["items"] + resposta_pagina_2.json()["items"]}
    assert "transm-0" not in numeros_retornados


def test_endpoint_rastreamento_nao_devolve_pedidos_com_fluxo_encerrado(sessao_teste, montar_client):
    industria = _criar_industria_teste(sessao_teste)
    _criar_pedido_com_status_erp(sessao_teste, industria, "transm-0", TipoStatusErp.TRANSMITIDO.value)
    _criar_pedido_com_status_erp(sessao_teste, industria, "conc-0", TipoStatusErp.PROCESSO_CONCLUIDO.value)
    _criar_pedido_com_status_erp(sessao_teste, industria, "canc-0", TipoStatusErp.PEDIDO_CANCELADO.value)

    client = montar_client(pedidos_router.router, nome_perfil="Operador Logístico")

    resposta = client.get("/pedidos/rastreamento", params={"page": 1, "size": 20})

    assert resposta.status_code == 200
    numeros = {item["numero_pedido_ol"] for item in resposta.json()["items"]}
    assert numeros == {"transm-0"}
