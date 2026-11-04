"""Registro dos layouts implementados: TipoLayout -> instância do layout."""
from ol_core.core.logger import logger
from ol_core.layouts.base import LayoutIntegracao, LayoutNaoSuportado, Operacao

_REGISTRO: dict = {}


def registrar(cls: type[LayoutIntegracao]) -> type[LayoutIntegracao]:
    """Decorador de classe: registra o layout pelo seu `tipo`."""
    if cls.tipo in _REGISTRO:
        raise ValueError(f"Layout {cls.tipo.value} registrado duas vezes.")
    _REGISTRO[cls.tipo] = cls()
    return cls


def layout_de(industria) -> LayoutIntegracao:
    """Layout da indústria. Levanta LayoutNaoSuportado se não houver
    implementação — nunca cai num layout padrão."""
    return layout_por_tipo(getattr(industria, "tipo_layout", None))


def _carregar_layouts() -> None:
    """Importa os módulos de layout (o import registra cada um via @registrar).

    Feito sob demanda, e não no __init__ do pacote: os services importam o
    formato (ol_core.layouts.formato_closeup) e o layout CloseUp importa os
    services — carregar tudo no import do pacote criaria um ciclo."""
    import ol_core.layouts.closeup  # noqa: F401


def layout_por_tipo(tipo) -> LayoutIntegracao:
    """Layout registrado para o TipoLayout. Levanta LayoutNaoSuportado se não houver."""
    _carregar_layouts()
    try:
        return _REGISTRO[tipo]
    except (KeyError, TypeError):
        raise LayoutNaoSuportado(tipo) from None


def layouts_registrados() -> frozenset:
    _carregar_layouts()
    return frozenset(_REGISTRO)


def industria_suporta(industria, operacao: Operacao) -> bool:
    """True se o layout da indústria está implementado e faz a operação.

    Os serviços automáticos chamam isto ANTES de tocar nos pedidos da
    indústria: reservar um pedido ("X Sendo Gerado") e só depois descobrir que
    o layout não gera o arquivo deixava o pedido travado até a trava expirar."""
    nome = getattr(industria, "nome", "?")
    try:
        layout = layout_de(industria)
    except LayoutNaoSuportado as erro:
        logger.warning(f"Indústria {nome}: {erro} — '{operacao.value}' não será processado.")
        return False
    if not layout.suporta(operacao):
        logger.warning(f"Indústria {nome}: layout {layout.tipo.value} não faz '{operacao.value}' — pulando.")
        return False
    return True
