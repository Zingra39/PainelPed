"""Layout Close-Up (Hypera): suporta todas as operações."""
from ol_core.layouts.base import LayoutIntegracao, Operacao
from ol_core.layouts.registro import registrar
from ol_core.models.enums.tipo_layout import TipoLayout
from ol_core.services.cancelamento_service import gerar_cancelado_closeup
from ol_core.services.espelho_service import gerar_espelho_closeup
from ol_core.services.estoque_service import gerar_estoque_closeup
from ol_core.services.retorno_service import gerar_retorno_closeup
from ol_core.utils.conversor import converter_arquivo_closeup


@registrar
class LayoutCloseup(LayoutIntegracao):
    tipo = TipoLayout.CLOSEUP
    operacoes = frozenset(Operacao)

    def ler_pedido(self, industria, arquivo: str):
        return converter_arquivo_closeup(industria, arquivo)

    def gerar_retorno(self, industria, pedido) -> bool:
        return gerar_retorno_closeup(industria, pedido)

    def gerar_espelho(self, industria, titulo) -> bool:
        return gerar_espelho_closeup(industria, titulo)

    def gerar_cancelamento(self, industria, pedido) -> bool:
        return gerar_cancelado_closeup(industria, pedido)

    def gerar_estoque(self, industria, pedido):
        return gerar_estoque_closeup(industria, pedido)
