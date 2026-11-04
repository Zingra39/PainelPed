"""Testes da rota GET /pedidos/{id}/gerar-pedido (reconstrução do arquivo
de pedido quando o original não está mais em disco).

Valida a reconstrução byte-a-byte contra o layout OFICIAL da Close-Up
("Docs/Layouts/Closeup/LAYOUT HYPERA CLOSE-UP RS006 - Manual Pedido
Indireto_v4.18.2.pdf", ANEXO I) — não contra o que o código já faz hoje.
Onde o código diverge do layout oficial, o teste fica com
`xfail(strict=True)` e o motivo cita a posição exata do manual, seguindo
a convenção já usada em test_espelho_service.py para gaps de spec
conhecidos. Isso documenta as pendências dos cards #42/#60 sem travar a
suíte, e vira um alerta (XPASS) automático no dia em que alguém corrigir
sem tirar o marcador.

Posições do ANEXO I (1-indexado, conforme o manual):
  CABEÇALHO (fixo, 247 caracteres):
    Tipo do registro       pos 1   len 1
    CNPJ da farmácia       pos 2   len 15
    Número do Pedido       pos 17  len 20
    Data do pedido         pos 37  len 8   (DDMMAAAA)
    Vago                   pos 45  len 3   (fixo "000")
    Tipo da Compra         pos 48  len 1
    Tipo do Retorno        pos 49  len 1   (fixo "C")
    Id. Linha de Produto   pos 50  len 1
    Compra Integral        pos 51  len 1   (fixo "0")
    CNPJ Distribuidor      pos 52  len 15
    Número OS              pos 67  len 20
    Observação             pos 87  len 100
    (... campos 187-247, fora do escopo desta rodada)
  DETALHE (122 caracteres):
    Tipo do registro       pos 1   len 1   (fixo "2")
    Número do pedido       pos 2   len 20
    EAN 13                 pos 22  len 13
    Quantidade             pos 35  len 5
    Condição Comercial     pos 40  len 4
    Desconto               pos 44  len 5
    (Prazo+Cond.Desconto+Cond.Prazo+Código do prazo: pos 49-93, 45 chars)
    Código da oferta       pos 94  len 20
    Preço                  pos 114 len 9
  RODAPÉ (36 caracteres):
    Tipo do registro       pos 1   len 1   (fixo "3")
    Número do Pedido       pos 2   len 20
    Quantidade de Itens    pos 22  len 5
    Quantidade de Unidades pos 27  len 10
"""
from datetime import datetime

import pytest

from app.routers import pedidos
from app.models import Pedido, PedidoItem
from .conftest import criar_pedido_e_industria


def _criar_pedido_com_item(sessao_teste, **dados_pedido):
    """Pedido de teste (sem arquivo original em disco, força a reconstrução)
    com 1 item, dados escolhidos para não bater com nenhum rjust/ljust por
    acidente (facilita enxergar erro de posição/largura nas asserções)."""
    padrao = dict(
        numero_pedido_ol="00000000000000000001",
        cnpj_cliente="12345678000199",
        data_pedido=datetime(2026, 8, 28),
        observacao="Entregar pela manha",
    )
    padrao.update(dados_pedido)
    pedido = criar_pedido_e_industria(sessao_teste, **padrao)
    item = PedidoItem(
        numero_pedido_ol=pedido.numero_pedido_ol,
        ean="7891234567895",
        quantidade_solicitada=10,
        desconto=12.5,
        id_cond=5,
    )
    sessao_teste.add(item)
    sessao_teste.commit()
    sessao_teste.refresh(pedido)
    return pedido


def _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido) -> list[str]:
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")
    resposta = client.get(f"/pedidos/{pedido.id}/gerar-pedido")
    assert resposta.status_code == 200
    return resposta.text.split("\r\n")


# --------------------------------------------------------------- CABEÇALHO

def test_cabecalho_cnpj_na_posicao_2_largura_15(sessao_teste, montar_client):
    pedido = _criar_pedido_com_item(sessao_teste)
    linhas = _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido)
    assert linhas[0][1:16] == "12345678000199 "


def test_cabecalho_numero_pedido_na_posicao_17_largura_20(sessao_teste, montar_client):
    pedido = _criar_pedido_com_item(sessao_teste)
    linhas = _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido)
    assert linhas[0][16:36] == pedido.numero_pedido_ol.ljust(20)


def test_cabecalho_vago_na_posicao_45_fixo_000(sessao_teste, montar_client):
    pedido = _criar_pedido_com_item(sessao_teste)
    linhas = _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido)
    assert linhas[0][44:47] == "000"


def test_cabecalho_data_pedido_na_posicao_37_formato_ddmmaaaa(sessao_teste, montar_client):
    pedido = _criar_pedido_com_item(sessao_teste)
    linhas = _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido)
    assert linhas[0][36:44] == "28082026"


def test_cabecalho_observacao_comeca_na_posicao_87(sessao_teste, montar_client):
    pedido = _criar_pedido_com_item(sessao_teste)
    linhas = _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido)
    assert linhas[0][86:] == "Entregar pela manha"


@pytest.mark.xfail(strict=True, reason=(
    "ANEXO I, pos. 87, Observação, X(100): o campo oficial tem 100 "
    "caracteres fixos. Hoje o código (achado em 2026-09-03, ver "
    "'observacao = observacao_valor if observacao_valor else " "') não "
    "faz NENHUM preenchimento — grava o texto puro, com largura variável "
    "conforme o tamanho da observação digitada. Isso já era um problema "
    "antes com ljust(20) só menos visível; agora, sem padding nenhum, "
    "outro campo com largura fixa que viesse depois da Observação no "
    "mesmo layout ficaria impossível de posicionar. Fica em aberto até o "
    "PO/Backend confirmarem se essa largura variável é intencional pra "
    "Hypera (como no ponto 4) ou se precisa ir para 100 fixos."
))
def test_cabecalho_observacao_tem_largura_100(sessao_teste, montar_client):
    pedido = _criar_pedido_com_item(sessao_teste)
    linhas = _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido)
    assert linhas[0][86:186] == "Entregar pela manha".ljust(100)


def test_observacao_vazia_nao_estoura_excecao(sessao_teste, montar_client):
    """Regressão simples (deve continuar passando mesmo depois de corrigir
    os xfails acima): pedido sem observação não pode quebrar o endpoint."""
    pedido = _criar_pedido_com_item(sessao_teste, observacao=None)
    linhas = _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido)
    assert len(linhas[0]) > 0


# ---------------------------------------------------------------- DETALHE

def test_detalhe_ean_na_posicao_22_largura_13(sessao_teste, montar_client):
    pedido = _criar_pedido_com_item(sessao_teste)
    linhas = _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido)
    assert linhas[1][21:34] == "7891234567895"


def test_detalhe_quantidade_na_posicao_35_largura_5(sessao_teste, montar_client):
    pedido = _criar_pedido_com_item(sessao_teste)
    linhas = _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido)
    assert linhas[1][34:39] == "00010"


def test_detalhe_desconto_na_posicao_44_largura_5(sessao_teste, montar_client):
    pedido = _criar_pedido_com_item(sessao_teste)
    linhas = _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido)
    assert linhas[1][43:48] == "01250"


@pytest.mark.xfail(strict=True, reason=(
    "Card #60, achado #3 (ANEXO I, pos. 94, Código da oferta, 9(20)): o "
    "código grava item.id_cond cru, sem zero-preenchimento pra 20 "
    "dígitos — além do bug de mapeamento já registrado no card (id_cond "
    "não é 'Condição Comercial', é lido de linha[93:98] no parser, que é "
    "na verdade o início do próprio campo 'Código da oferta')."
))
def test_detalhe_codigo_da_oferta_na_posicao_94_largura_20(sessao_teste, montar_client):
    pedido = _criar_pedido_com_item(sessao_teste)
    linhas = _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido)
    assert linhas[1][93:113] == "5".rjust(20, "0")


@pytest.mark.xfail(strict=True, reason=(
    "Card #60, achado #2 (ANEXO I, pos. 114, Preço, 9(7,2)): o campo "
    "Preço não é gravado — a linha de detalhe termina logo após o "
    "'Código da oferta', 28 caracteres mais curta que os 122 exigidos."
))
def test_detalhe_tem_122_caracteres_fixos(sessao_teste, montar_client):
    pedido = _criar_pedido_com_item(sessao_teste)
    linhas = _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido)
    assert len(linhas[1]) == 122


# ---------------------------------------------------------------- RODAPÉ

@pytest.mark.xfail(strict=True, reason=(
    "Card #60, achado #4 (ANEXO I, pos. 22, Quantidade de Itens, 9(5)): "
    "o rodapé hoje grava a CONTAGEM DE LINHAS DO ARQUIVO (cabeçalho + "
    "itens + rodapé) nessa posição, não a quantidade de itens do pedido. "
    "Para 1 item, deveria gravar '00001', grava '00003'."
))
def test_rodape_quantidade_de_itens_na_posicao_22_largura_5(sessao_teste, montar_client):
    pedido = _criar_pedido_com_item(sessao_teste)
    linhas = _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido)
    assert linhas[2][21:26] == "00001"


@pytest.mark.xfail(strict=True, reason=(
    "Card #60, achado #4 (ANEXO I, pos. 27, Quantidade de Unidades, "
    "9(10)): o rodapé hoje grava a CONTAGEM DE ITENS (5 dígitos) nessa "
    "posição, em vez da SOMA das quantidades solicitadas (10 dígitos). "
    "Para 1 item com quantidade_solicitada=10, deveria gravar "
    "'0000000010', grava '00001'."
))
def test_rodape_quantidade_de_unidades_na_posicao_27_largura_10(sessao_teste, montar_client):
    pedido = _criar_pedido_com_item(sessao_teste)
    linhas = _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido)
    assert linhas[2][26:36] == str(10).rjust(10, "0")


@pytest.mark.xfail(strict=True, reason=(
    "Card #60: o rodapé oficial (ANEXO I) tem largura FIXA de 36 "
    "caracteres. Hoje sai mais curto (faltam os dígitos de Quantidade de "
    "Unidades, que deveria ter 10 dígitos e não 5)."
))
def test_rodape_tem_36_caracteres_fixos(sessao_teste, montar_client):
    pedido = _criar_pedido_com_item(sessao_teste)
    linhas = _gerar_e_extrair_linhas(sessao_teste, montar_client, pedido)
    assert len(linhas[2]) == 36


# ------------------------------------------------------- CARD #42 (aviso)

@pytest.mark.xfail(strict=True, reason=(
    "Card #42: quando o arquivo é reconstruído (não é o original em "
    "disco), o backend precisa sinalizar isso de algum jeito explícito "
    "(ex.: header de resposta) pro frontend poder avisar o operador. Hoje "
    "a resposta da reconstrução não carrega nenhuma indicação disso — só "
    "Content-Disposition/Content-Type iguais ao caso do arquivo original."
))
def test_resposta_reconstruida_sinaliza_que_nao_e_o_arquivo_original(sessao_teste, montar_client):
    pedido = _criar_pedido_com_item(sessao_teste)
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")
    resposta = client.get(f"/pedidos/{pedido.id}/gerar-pedido")
    assert resposta.status_code == 200
    assert any("reconstru" in nome.lower() for nome in resposta.headers.keys())


# --------------------------------------------------------- CASOS DE ERRO

def test_endpoint_sem_token_retorna_401(montar_client):
    client = montar_client(pedidos.router, nome_perfil=None)
    resposta = client.get("/pedidos/1/gerar-pedido")
    assert resposta.status_code == 401


def test_endpoint_com_perfil_sem_permissao_retorna_403(montar_client):
    client = montar_client(pedidos.router, nome_perfil="Gerente Comercial")
    resposta = client.get("/pedidos/1/gerar-pedido")
    assert resposta.status_code == 403


def test_endpoint_com_pedido_inexistente_retorna_404(montar_client):
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")
    resposta = client.get("/pedidos/999999/gerar-pedido")
    assert resposta.status_code == 404


def test_endpoint_com_pedido_sem_itens_retorna_422(sessao_teste, montar_client):
    pedido = criar_pedido_e_industria(sessao_teste)
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")
    resposta = client.get(f"/pedidos/{pedido.id}/gerar-pedido")
    assert resposta.status_code == 422


def test_endpoint_com_arquivo_original_em_disco_devolve_o_arquivo_intacto(sessao_teste, montar_client, tmp_path):
    """Regressão: quando o arquivo original AINDA existe em disco, o
    endpoint deve devolvê-lo byte a byte, sem passar pela reconstrução —
    nenhum dos bugs acima deve poder afetar esse caminho."""
    from app.models import Arquivo

    conteudo_original = "1CONTEUDO-ORIGINAL-BYTE-A-BYTE-NAO-RECONSTRUIDO\r\n"
    caminho_arquivo = tmp_path / "PEDIDO_ORIGINAL.txt"
    # newline="" desativa a tradução universal de fim de linha do Path.write_text:
    # sem isso, no Windows, o \n já presente em conteudo_original (que termina em
    # \r\n) seria traduzido de novo para \r\n, gravando \r\r\n em disco.
    caminho_arquivo.write_text(conteudo_original, encoding="utf-8", newline="")

    pedido = _criar_pedido_com_item(sessao_teste)
    arquivo = Arquivo(
        numero_pedido_ol=pedido.numero_pedido_ol,
        tipo="pedido",
        nome="PEDIDO_ORIGINAL.txt",
        caminho=str(caminho_arquivo),
        situacao="PROCESSADO",
    )
    sessao_teste.add(arquivo)
    sessao_teste.commit()

    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")
    resposta = client.get(f"/pedidos/{pedido.id}/gerar-pedido")

    assert resposta.status_code == 200
    assert resposta.text == conteudo_original


# --------------------------------------------------------------- golden (bytes)
# Trava a reconstrução byte a byte (inclusive as divergências do manual
# documentadas acima com xfail): a montagem saiu do router para
# ol_core/layouts/formato_closeup.py sem mudar nada. Regerar só com mudança
# intencional: OL_GOLDEN_ATUALIZAR=1 pytest OL_TEST/api/test_gerar_pedido_router.py

def test_reconstrucao_igual_ao_golden(sessao_teste, montar_client):
    import os
    from pathlib import Path

    pedido = _criar_pedido_com_item(sessao_teste, observacao=None, cnpj_cliente="57107095000164")
    sessao_teste.add(PedidoItem(
        numero_pedido_ol=pedido.numero_pedido_ol, ean="789123", quantidade_solicitada=240,
        desconto=33.335, id_cond=None,
    ))
    sessao_teste.commit()
    sessao_teste.refresh(pedido)

    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")
    conteudo = client.get(f"/pedidos/{pedido.id}/gerar-pedido").content

    golden = Path(__file__).resolve().parent.parent / "golden" / "closeup" / "pedido_reconstruido.txt"
    if os.getenv("OL_GOLDEN_ATUALIZAR") == "1":
        golden.write_bytes(conteudo)
    assert conteudo == golden.read_bytes()
