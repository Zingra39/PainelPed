"""Orquestra as operações manuais que disparam funções do ol_core.

Fachada do pacote: os routers usam `operacoes.<função>` e devem continuar
usando só o que está listado aqui. A implementação fica dividida por
responsabilidade:

    conversao        registros ORM -> modelos do ol_core; pastas do OL_Services
    historico        registro das ações no histórico do pedido
    geracao          retorno, espelho e cancelamento (ERP) + travas de status
    reprocessamento  reimportação/revalidação do arquivo do pedido
    envio            transmissão para o ERP e reenvio por FTP
    exibicao         rótulo de status dos arquivos na tela
    titulo_erp       título (NF) do pedido no ERP

Testes que precisam isolar um colaborador interno (ex.: `gerar_retorno_closeup`)
devem fazer o monkeypatch no módulo que o usa (`operacoes.geracao`), não aqui.
"""
from .envio import executar_reenviar_arquivo, executar_transmitir
from .exibicao import mapear_status_arquivo
from .geracao import (
    LIMITE_RETORNO_MANUAL,
    acoes_de_geracao_manual,
    executar_cancelamento,
    executar_gerar_espelho,
    executar_gerar_retorno,
    retorno_manual_liberado_por_atraso,
)
from .historico import registrar_log_analise, registrar_log_observacao
from .reprocessamento import executar_reprocessar
from .titulo_erp import buscar_titulo_erp

__all__ = [
    "LIMITE_RETORNO_MANUAL",
    "acoes_de_geracao_manual",
    "buscar_titulo_erp",
    "executar_cancelamento",
    "executar_gerar_espelho",
    "executar_gerar_retorno",
    "executar_reenviar_arquivo",
    "executar_reprocessar",
    "executar_transmitir",
    "mapear_status_arquivo",
    "registrar_log_analise",
    "registrar_log_observacao",
    "retorno_manual_liberado_por_atraso",
]
