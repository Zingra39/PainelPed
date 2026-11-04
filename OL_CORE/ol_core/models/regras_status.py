"""Tabela única das regras "a partir de qual status o pedido pode X".

Toda regra que decide uma operação pelo status do pedido mora aqui — core,
API e serviços importam daqui em vez de declarar o próprio conjunto. Para
mudar uma regra (ex.: liberar o espelho manual em mais um status), altera-se
só esta tabela.

Os valores são os textos gravados nas colunas (`TipoStatusOper.X.value` /
`TipoStatusErp.X.value`), prontos para `in` em Python e `.in_()` no SQLAlchemy.

O que NÃO está aqui: a ordem das etapas dentro de cada operação (ex.: "Sendo
Gerado" -> "Gerado" / falha), que continua no código da operação.
"""
from ol_core.models.enums.tipo_status_erp import TipoStatusErp as _Erp
from ol_core.models.enums.tipo_status_oper import TipoStatusOper as _Oper


def _oper(*membros: _Oper) -> frozenset[str]:
    return frozenset(m.value for m in membros)


def _erp(*membros: _Erp) -> frozenset[str]:
    return frozenset(m.value for m in membros)


# ------------------------------------------------------------ status_operacional

# Geração (automática ou manual) em andamento: quem está neles detém o pedido
# até gravar o status final; nenhuma outra geração pode começar.
EM_GERACAO = _oper(_Oper.GERANDO_RETORNO, _Oper.GERANDO_ESPELHO, _Oper.GERANDO_CANCELAMENTO)

# Falhas de uma etapa de geração (inclui o FALHA genérico de dados legados).
FALHAS_GERACAO = _oper(_Oper.FALHA, _Oper.FALHA_RETORNO, _Oper.FALHA_ESPELHO, _Oper.FALHA_CANCELAMENTO)

# Geração MANUAL pelo painel: só depois que o serviço automático gerou o arquivo
# (regerar) ou quando a geração falhou (a nova tentativa é só manual).
# O retorno também pode ser regerado depois que o pedido avançou para Espelho
# ou Cancelamento; e é liberado por atraso (ver AGUARDANDO_RETORNO).
PODE_GERAR_RETORNO_MANUAL = _oper(_Oper.RETORNO, _Oper.ESPELHO, _Oper.CANCELADO, _Oper.FALHA_RETORNO)
PODE_GERAR_ESPELHO_MANUAL = _oper(_Oper.ESPELHO, _Oper.FALHA_ESPELHO)
PODE_GERAR_CANCELAMENTO_MANUAL = _oper(_Oper.CANCELADO, _Oper.FALHA_CANCELAMENTO)

# Regerar o retorno a partir destes status mantém o status (o pedido não
# "regride" na esteira); a partir dos demais, o sucesso leva a "Retorno Gerado".
RETORNO_REGERADO_MANTEM_STATUS = PODE_GERAR_RETORNO_MANUAL - _oper(_Oper.FALHA_RETORNO)

# Transmitido e ainda sem retorno: depois do prazo, a geração manual é liberada.
AGUARDANDO_RETORNO = _oper(_Oper.TRANSMITIDO, _Oper.AGUARDANDO_RETORNO)

# "Em Analise": só entra quem está na fila da triagem, e o encerramento
# (reprocessamento) só é válido se devolver o pedido a um desses status.
PODE_ENTRAR_EM_ANALISE = _oper(_Oper.PRONTO, _Oper.VERIFICAR)
RESULTADO_VALIDO_POS_ANALISE = PODE_ENTRAR_EM_ANALISE

# Reprocessamento em lote "só os com erro".
REPROCESSAR_EM_LOTE_COM_ERRO = _oper(_Oper.FALHA, _Oper.VERIFICAR, _Oper.FALHA_REPROCESSAMENTO)


# ------------------------------------------------------------ status_erp

# Fluxo encerrado: sai do Rastreamento e vai para o Histórico.
ERP_ENCERRADO = _erp(_Erp.PROCESSO_CONCLUIDO, _Erp.PEDIDO_CANCELADO)

# Lotes de geração por período.
ERP_ESPELHO_EM_LOTE = _erp(_Erp.AGUARDANDO_FATURAMENTO)
ERP_CANCELAMENTO_EM_LOTE = _erp(_Erp.TRANSMITIDO, _Erp.AGUARDANDO_FATURAMENTO)

# Cancelamento manual: pedido já faturado é cancelado direto no ERP.
ERP_CANCELAMENTO_MANUAL_BLOQUEADO = _erp(_Erp.PROCESSO_CONCLUIDO)
