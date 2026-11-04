"""Tradução de (tipo, situação) da tabela `arquivo` para o rótulo exibido no painel."""
from ol_core.models.enums.tipo_arquivo import TipoArquivo
from ol_core.models.enums.tipo_status_oper import TipoStatusOper


_ROTULO_TIPO = {
    TipoArquivo.RETORNO.value: "Retorno",
    TipoArquivo.ESPELHO.value: "Espelho",
    TipoArquivo.CANCELADO.value: "Cancelamento",
}


# Situações gravadas pelos services (retorno_service/espelho_service/
# cancelamento_service) usando os próprios valores de TipoStatusOper — já
# batem 1:1 com o rótulo que o painel exibe, então são reconhecidas direto,
# sem tradução (inclui as falhas específicas por etapa: Falha no Retorno/
# Espelho/Cancelamento, que substituíram o FALHA genérico nesses 3 services).
_SITUACOES_RECONHECIDAS = {
    TipoStatusOper.GERANDO_RETORNO.value,
    TipoStatusOper.RETORNO.value,
    TipoStatusOper.FALHA_RETORNO.value,
    TipoStatusOper.GERANDO_ESPELHO.value,
    TipoStatusOper.ESPELHO.value,
    TipoStatusOper.FALHA_ESPELHO.value,
    TipoStatusOper.GERANDO_CANCELAMENTO.value,
    TipoStatusOper.CANCELADO.value,
    TipoStatusOper.FALHA_CANCELAMENTO.value,
}


def mapear_status_arquivo(tipo: str, situacao: str) -> "str | None":
    """Traduz (tipo, situacao) da tabela `arquivo` para o rótulo de exibição do painel."""
    rotulo_tipo = _ROTULO_TIPO.get((tipo or "").lower())
    if not rotulo_tipo or not situacao:
        return None

    # Situação já gravada no formato final de exibição — usa direto.
    if situacao in _SITUACOES_RECONHECIDAS:
        return situacao

    # Fallback pra dados legados, gravados antes desses valores baterem 1:1
    # com TipoStatusOper (situacao só com "gerado"/"erro"/"enviado"/"em criação").
    situacao_norm = situacao.strip().lower()
    if situacao_norm == "erro":
        return TipoStatusOper.FALHA.value
    if situacao_norm in ("em criação", "recriando"):
        return f"Gerando {rotulo_tipo}"
    if situacao_norm == "gerado":
        return f"{rotulo_tipo} Gerado"
    if situacao_norm == "enviado":
        return f"{rotulo_tipo} Enviado"
    return None
