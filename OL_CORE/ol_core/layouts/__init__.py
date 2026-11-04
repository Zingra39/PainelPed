"""Layouts de integração.

- `base`: contrato (`LayoutIntegracao`, `Operacao`) e exceções;
- `registro`: `layout_de(industria)` / `industria_suporta(...)`;
- `formato_<layout>`: formato puro dos arquivos (posições e larguras, sem I/O);
- `<layout>`: a classe registrada, que liga o formato aos services.

Para adicionar um layout: criar o módulo com a classe decorada por
`@registrar` e importá-lo em `registro._carregar_layouts` (os layouts são
carregados sob demanda — ver o motivo lá).
"""
from ol_core.layouts.base import LayoutIntegracao, LayoutNaoSuportado, Operacao, OperacaoNaoSuportada
from ol_core.layouts.registro import industria_suporta, layout_de, layout_por_tipo, layouts_registrados, registrar

__all__ = [
    "LayoutIntegracao",
    "LayoutNaoSuportado",
    "industria_suporta",
    "Operacao",
    "OperacaoNaoSuportada",
    "layout_de",
    "layout_por_tipo",
    "layouts_registrados",
    "registrar",
]
