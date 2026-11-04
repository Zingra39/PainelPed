"""ol_core.layouts.formato_closeup: formato puro do Close-Up.

O conteúdo dos arquivos está travado pelos golden files (test_golden_closeup.py
e api/test_gerar_pedido_router.py). Aqui: a pureza do módulo (não pode puxar
banco, ERP ou FTP) e que nenhuma ordem de import cria ciclo entre o formato,
os services e o registro de layouts.
"""
import subprocess
import sys

import pytest

from ol_core.layouts import formato_closeup as formato


def _rodar(codigo: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True)


def test_formato_nao_importa_banco_erp_nem_ftp():
    resultado = _rodar(
        "import sys, ol_core.layouts.formato_closeup\n"
        "proibidos = [m for m in sys.modules if m.startswith(("
        "'ol_core.database', 'ol_core.services', 'pymysql', 'pyodbc', 'sqlalchemy', 'ftplib'))]\n"
        "print(proibidos)"
    )
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.strip() == "[]"


@pytest.mark.parametrize("primeiro", [
    "ol_core.layouts",
    "ol_core.layouts.formato_closeup",
    "ol_core.layouts.closeup",
    "ol_core.services.retorno_service",
    "ol_core.services.espelho_service",
    "ol_core.services.cancelamento_service",
    "ol_core.services.estoque_service",
    "ol_core.services.import_service",
    "ol_core.utils.conversor",
    "ol_core.utils.transmissao",
])
def test_nenhuma_ordem_de_import_cria_ciclo(primeiro):
    resultado = _rodar(
        f"import {primeiro}\n"
        "from ol_core.layouts import layout_de, Operacao\n"
        "from ol_core.models.enums.tipo_layout import TipoLayout\n"
        "from types import SimpleNamespace\n"
        "assert layout_de(SimpleNamespace(tipo_layout=TipoLayout.CLOSEUP)).suporta(Operacao.RETORNO)\n"
    )
    assert resultado.returncode == 0, resultado.stderr


@pytest.mark.parametrize("texto, valor", [("08666", 86.66), ("00000", 0.0), ("10000", 100.0), ("01250", 12.5)])
def test_desconto_ida_e_volta(texto, valor):
    assert formato.converter_desconto_str_float(texto) == valor
    assert formato.converter_desconto_float_str(valor) == texto


def test_conversor_continua_exportando_as_funcoes_de_desconto():
    from ol_core.utils import conversor

    assert conversor.converter_desconto_float_str is formato.converter_desconto_float_str
    assert conversor.converter_desconto_str_float is formato.converter_desconto_str_float


def test_aplicar_observacao_grava_nas_posicoes_87_a_186():
    cabecalho = "1" + "X" * 100  # mais curto que o campo
    novo = formato.aplicar_observacao(cabecalho, "ENTREGAR CEDO")

    assert novo[:86] == cabecalho[:86]
    assert novo[86:186] == "ENTREGAR CEDO".ljust(100)
    assert formato.ler_cabecalho_pedido(novo)["observacao"] == "ENTREGAR CEDO"


def test_aplicar_observacao_corta_no_limite_do_campo():
    novo = formato.aplicar_observacao(" " * 247, "A" * 150)

    assert novo[86:186] == "A" * 100
    assert len(novo) == 247


def test_cnpj_do_nome_arquivo():
    assert formato.cnpj_do_nome_arquivo("PEDIDO_123_57107095000164.txt") == "57107095000164"
    assert formato.cnpj_do_nome_arquivo("PEDIDO_123_99.txt") == "00000000000099"
    assert formato.cnpj_do_nome_arquivo("PEDIDO_123.txt") is None
