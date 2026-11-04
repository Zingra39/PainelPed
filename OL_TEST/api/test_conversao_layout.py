"""app.services.operacoes.conversao._layout: sem fallback silencioso para CloseUp.

Antes, layout vazio ou desconhecido virava CloseUp e a API gerava/relia o
arquivo no formato errado. Agora é erro com mensagem clara — o mesmo que o
core já faz ao carregar a indústria nos serviços automáticos.
"""
import pytest

from app.services.operacoes.conversao import _layout
from ol_core.models.enums.tipo_layout import TipoLayout


@pytest.mark.parametrize("valor, esperado", [
    ("closeup", TipoLayout.CLOSEUP),
    ("CloseUp", TipoLayout.CLOSEUP),
    (" closeup ", TipoLayout.CLOSEUP),
    ("focopdv", TipoLayout.FOCOPDV),
    ("tudofarma", TipoLayout.TUDOFARMA),
])
def test_layout_reconhecido(valor, esperado):
    assert _layout(valor) is esperado


@pytest.mark.parametrize("valor", [None, "", "close up", "hypera"])
def test_layout_vazio_ou_desconhecido_e_erro(valor):
    with pytest.raises(ValueError, match="não reconhecido"):
        _layout(valor)
