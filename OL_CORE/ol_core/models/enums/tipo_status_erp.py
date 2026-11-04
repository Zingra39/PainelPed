from enum import Enum


class TipoStatusErp(Enum):
    """Status do pedido do ponto de vista comercial/faturamento — coluna `status_erp`.

    Distinto de TipoStatusOper (coluna status_operacional), que rastreia a
    etapa operacional detalhada de cada geração (ex.: "Retorno Sendo
    Gerado", "Falha no Espelho"). Aqui o pedido só percorre 5 estágios do
    ponto de vista do faturamento, sempre nesta ordem:

        Não Transmitido -> Transmitido -> Aguardando Faturamento
            -> Pedido Concluido (Espelho gerado, pedido faturado)
            -> Pedido Cancelado (Cancelamento gerado)

    Pedido Concluido e Pedido Cancelado são estágios finais: a partir
    deles o pedido sai da tela de Rastreamento e passa a aparecer só na
    tela de Histórico (ver `_filtrar_rastreamento` e o endpoint
    `/pedidos/historico` em app/routers/pedidos.py).
    """
    NAO_TRANSMITIDO = "Não Transmitido"  # Pedido ainda não transmitido pro ERP/DELAGE
    TRANSMITIDO = "Transmitido"  # Pedido transmitido, aguardando geração do Retorno
    AGUARDANDO_FATURAMENTO = "Aguardando Faturamento"  # Retorno gerado — aguardando o Espelho (faturamento) ou o Cancelamento
    PROCESSO_CONCLUIDO = "Pedido Concluido"  # Espelho gerado — pedido faturado, fluxo encerrado
    PEDIDO_CANCELADO = "Pedido Cancelado"  # Cancelamento gerado — fluxo encerrado
