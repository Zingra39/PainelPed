"""Contrato de um layout de integração (formato de arquivo de uma indústria).

Cada layout declara as operações que suporta; quem orquestra (import_service,
serviços automáticos, API) pede o layout ao registro (`layout_de`) em vez de
testar `if layout == CLOSEUP`. Um layout novo é uma classe nova registrada —
nenhum `if` muda.

Hoje as operações do CloseUp ainda delegam para as funções `*_closeup`
existentes. O próximo passo (Auditoria, seção 4.3) é trazer para dentro do
layout só o FORMATO (ler/escrever texto), deixando a orquestração comum.
"""
from abc import ABC
from enum import Enum
from typing import ClassVar

from ol_core.models.enums.tipo_layout import TipoLayout


class Operacao(Enum):
    PEDIDO = "pedido"  # ler o arquivo de pedido da indústria
    RETORNO = "retorno"
    ESPELHO = "espelho"
    CANCELAMENTO = "cancelamento"
    ESTOQUE = "estoque"


class LayoutNaoSuportado(Exception):
    """A indústria usa um layout sem implementação registrada."""

    def __init__(self, tipo_layout):
        self.tipo_layout = tipo_layout
        valor = getattr(tipo_layout, "value", tipo_layout)
        super().__init__(f"Layout desconhecido: {valor}")


class OperacaoNaoSuportada(Exception):
    """O layout existe, mas não implementa a operação pedida."""

    def __init__(self, tipo_layout: TipoLayout, operacao: Operacao):
        self.tipo_layout = tipo_layout
        self.operacao = operacao
        super().__init__(f"Layout {tipo_layout.value} não suporta a operação '{operacao.value}'.")


class LayoutIntegracao(ABC):
    tipo: ClassVar[TipoLayout]
    operacoes: ClassVar[frozenset[Operacao]]

    def suporta(self, operacao: Operacao) -> bool:
        return operacao in self.operacoes

    def _nao_suporta(self, operacao: Operacao):
        raise OperacaoNaoSuportada(self.tipo, operacao)

    # Cada layout sobrescreve as operações que declara em `operacoes`.

    def ler_pedido(self, industria, arquivo: str):
        """Converte o arquivo de pedido em `Pedido` (ou None se não conseguir)."""
        self._nao_suporta(Operacao.PEDIDO)

    def gerar_retorno(self, industria, pedido) -> bool:
        self._nao_suporta(Operacao.RETORNO)

    def gerar_espelho(self, industria, titulo) -> bool:
        self._nao_suporta(Operacao.ESPELHO)

    def gerar_cancelamento(self, industria, pedido) -> bool:
        self._nao_suporta(Operacao.CANCELAMENTO)

    def gerar_estoque(self, industria, pedido):
        self._nao_suporta(Operacao.ESTOQUE)
