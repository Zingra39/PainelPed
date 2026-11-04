"""Rotas de /pedidos, divididas por responsabilidade.

    consulta           listagens paginadas (pedidos, Triagem, Rastreamento, Histórico)
    exportacao         xlsx das listagens
    lote               operações em lote e seus /preview
    analise            entrada/saída do status "Em Analise"
    operacoes_manuais  retorno, espelho, reprocessar, observação, transmitir, cancelamento
    layout             download do arquivo do pedido no layout do distribuidor
    detalhe            GET /{id} e /{id}/detalhes

Helpers compartilhados ficam em `_comum` e `_rastreamento`.

A ORDEM de inclusão importa: `detalhe` tem o `GET /pedidos/{id}`, que casaria
com /pedidos/confeccao, /pedidos/rastreamento etc. se viesse antes delas —
por isso entra por último.
"""
from fastapi import APIRouter

from . import analise, consulta, detalhe, exportacao, layout, lote, operacoes_manuais

router = APIRouter()
for _modulo in (consulta, exportacao, lote, analise, operacoes_manuais, layout, detalhe):
    router.include_router(_modulo.router)
