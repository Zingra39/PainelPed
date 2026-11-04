"""I10: validação dos parâmetros de configuração antes de gravar (PUT /parametros)."""
import pytest

from app.routers.parametros import cnpj_valido, normalizar_valor


@pytest.mark.parametrize("cnpj, ok", [
    ("11222333000181", True),
    ("11222333000182", False),   # dígito verificador errado
    ("11111111111111", False),   # todos iguais
    ("1122233300018", False),    # 13 dígitos
])
def test_cnpj_valido(cnpj, ok):
    assert cnpj_valido(cnpj) is ok


def test_cnpj_distribuidor_aceita_mascara_e_grava_so_digitos():
    assert normalizar_valor("cnpj_distribuidor", "11.222.333/0001-81") == "11222333000181"


def test_cnpj_distribuidor_invalido_ou_vazio_e_recusado():
    with pytest.raises(ValueError):
        normalizar_valor("cnpj_distribuidor", "11.222.333/0001-82")
    with pytest.raises(ValueError):
        normalizar_valor("cnpj_distribuidor", "")


def test_filiais_normaliza_lista_e_vazio_vira_nao_configurado():
    assert normalizar_valor("filiais_estoque", "12328; 12329 12328") == "12328,12329"
    assert normalizar_valor("filiais_estoque", "") is None


def test_filiais_com_codigo_invalido_e_recusado():
    with pytest.raises(ValueError, match="abc"):
        normalizar_valor("filiais_estoque", "12328, abc")


def test_demais_parametros_continuam_sem_aceitar_vazio():
    assert normalizar_valor("limitador_de_envio", "250") == "250"
    with pytest.raises(ValueError):
        normalizar_valor("limitador_de_envio", "")
