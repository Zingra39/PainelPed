"""Testes de ol_core.utils.transmissao.copiar_arquivo_com_observacao —
função de cópia do arquivo do pedido pra pasta de entrada, centralizada em
OL_CORE (Card de transmissão automática, squad review 2026-09-17) pra ser
usada tanto pela transmissão manual (OL_API/app/services/operacoes/envio.py)
quanto pela automática (ol_core/services/import_service.py).

Migrada de app/services/operacoes.py::_copiar_com_observacao sem mudança de
lógica — estes testes cobrem código que antes não tinha teste dedicado.
"""
from ol_core.utils.transmissao import copiar_arquivo_com_observacao

_OBSERVACAO = "Observação de teste"


def test_sem_observacao_copia_o_arquivo_byte_a_byte(tmp_path):
    origem = tmp_path / "origem.txt"
    conteudo = ("1" + "A" * 300 + "\r\n" + "2" + "B" * 50 + "\r\n").encode("utf-8")
    origem.write_bytes(conteudo)
    destino = tmp_path / "destino.txt"

    copiar_arquivo_com_observacao(str(origem), str(destino), "")

    # Sem observação, a cópia é byte a byte — nem os terminadores de linha
    # são tocados.
    assert destino.read_bytes() == origem.read_bytes()


def test_com_observacao_sobrescreve_so_o_campo_no_cabecalho(tmp_path):
    cabecalho = "1" + "A" * 300  # 301 caracteres — cobre o campo [86:186]
    segunda_linha = "2" + "B" * 50
    origem = tmp_path / "origem.txt"
    origem.write_text(cabecalho + "\n" + segunda_linha, encoding="utf-8", newline="")
    destino = tmp_path / "destino.txt"

    copiar_arquivo_com_observacao(str(origem), str(destino), _OBSERVACAO)

    nova_primeira_linha, novo_resto = destino.read_text(encoding="utf-8", newline="").split("\n", 1)

    # Campo da observação (posições 87 a 186, 0-based [86:186]) foi sobrescrito.
    assert nova_primeira_linha[86:86 + len(_OBSERVACAO)] == _OBSERVACAO
    # Fora do campo, o cabeçalho continua idêntico ao original.
    assert nova_primeira_linha[:86] == cabecalho[:86]
    # A partir da 2ª linha, o arquivo nunca é tocado.
    assert novo_resto == segunda_linha


def test_observacao_mais_curta_que_o_campo_e_preenchida_com_espacos(tmp_path):
    cabecalho = "1" + "A" * 300
    origem = tmp_path / "origem.txt"
    origem.write_text(cabecalho, encoding="utf-8", newline="")
    destino = tmp_path / "destino.txt"

    copiar_arquivo_com_observacao(str(origem), str(destino), "curta")

    campo = destino.read_text(encoding="utf-8", newline="")[86:186]
    assert campo == "curta".ljust(100)


def test_observacao_maior_que_o_campo_e_truncada_em_100_caracteres(tmp_path):
    cabecalho = "1" + "A" * 300
    origem = tmp_path / "origem.txt"
    origem.write_text(cabecalho, encoding="utf-8", newline="")
    destino = tmp_path / "destino.txt"
    observacao_longa = "X" * 150

    copiar_arquivo_com_observacao(str(origem), str(destino), observacao_longa)

    campo = destino.read_text(encoding="utf-8", newline="")[86:186]
    assert campo == "X" * 100
    assert len(campo) == 100


def test_preserva_o_terminador_cr_da_primeira_linha(tmp_path):
    cabecalho = "1" + "A" * 300
    origem = tmp_path / "origem.txt"
    origem.write_text(cabecalho + "\r\n2" + "B" * 20, encoding="utf-8", newline="")
    destino = tmp_path / "destino.txt"

    copiar_arquivo_com_observacao(str(origem), str(destino), "obs")

    primeira_linha = destino.read_text(encoding="utf-8", newline="").split("\n", 1)[0]
    assert primeira_linha.endswith("\r")
