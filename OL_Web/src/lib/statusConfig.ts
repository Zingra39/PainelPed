/**
 * Fonte única de cores e regras de status do front (F6 da auditoria).
 *
 * Antes o `StatusBadge` e o `RASTREAMENTO_COLORS` do Rastreamento pintavam o
 * mesmo status com cores diferentes. As regras de "pode gerar" vêm da API
 * (campos `pode_gerar_*`), não de listas de status daqui. A regra de cor é por estágio, igual
 * para retorno, espelho e cancelamento:
 *   gerando = azul · gerado = ciano · enviado = verde · falha = vermelho forte
 */

export const STATUS_STYLES: Record<string, string> = {
  // status_operacional (valores reais retornados pela API — ver TipoStatusOper)
  'Importado':                    'bg-slate-100 text-slate-600',
  'Validando':                    'bg-blue-100 text-blue-700',
  'Verificar':                    'bg-red-100 text-red-700',
  // Pedido que um operador marcou como em análise na triagem (valor sem
  // acento — ver exibirStatus em lib/statusEnum.ts).
  'Em Analise':                   'bg-violet-100 text-violet-700',
  'Reprocessando':                'bg-amber-100 text-amber-700',
  'Falha no Reprocessamento':     'bg-red-200 text-red-800',
  'Pendência Operacional':        'bg-amber-100 text-amber-700',
  'Aguardando Reprocessamento':   'bg-blue-100 text-blue-700',
  'Pronto':                       'bg-green-100 text-green-700',
  'Pronto para Processamento':    'bg-lime-100 text-lime-700',
  'Processado':                   'bg-green-100 text-green-700',
  'Transmitindo':                 'bg-blue-100 text-blue-700',
  'Gerando Retorno':              'bg-blue-100 text-blue-700',
  'Retorno Gerado':               'bg-cyan-100 text-cyan-700',
  'Retorno Enviado':              'bg-green-100 text-green-700',
  'Gerando Espelho':              'bg-blue-100 text-blue-700',
  'Espelho Gerado':               'bg-cyan-100 text-cyan-700',
  'Espelho Enviado':              'bg-green-100 text-green-700',
  'Cancelando':                   'bg-red-100 text-red-700',
  'Cancelado':                    'bg-orange-100 text-orange-700',
  'Gerando Cancelamento':         'bg-blue-100 text-blue-700',
  'Cancelamento Gerado':          'bg-cyan-100 text-cyan-700',
  'Cancelamento Enviado':         'bg-green-100 text-green-700',
  'Falha':                        'bg-red-200 text-red-800',
  'Falha no Retorno':             'bg-red-200 text-red-800',
  'Falha no Espelho':             'bg-red-200 text-red-800',
  'Falha no Cancelamento':        'bg-red-200 text-red-800',
  // status_erp (ver TipoStatusErp)
  'Não Transmitido':              'bg-slate-100 text-slate-600',
  'Transmitido':                  'bg-blue-100 text-blue-700',
  'Aguardando Faturamento':       'bg-amber-100 text-amber-700',
  'Pedido Concluido':             'bg-green-100 text-green-700',
  'Pedido Cancelado':             'bg-orange-100 text-orange-700',
  // severidade ocorrência
  'INFO':                         'bg-blue-100 text-blue-700',
  'ALERTA':                       'bg-amber-100 text-amber-700',
  'ERRO':                         'bg-red-100 text-red-700',
  'CRITICO':                      'bg-red-200 text-red-800',
  '0':                            'bg-slate-100 text-slate-600',
  // arquivo situacao
  'Pendente':                     'bg-slate-100 text-slate-600',
  'Enviado':                      'bg-green-100 text-green-700',
  'Erro':                         'bg-red-100 text-red-700',
}

export const STATUS_STYLE_PADRAO = 'bg-slate-100 text-slate-600'

export const estiloStatus = (status: string) => STATUS_STYLES[status] ?? STATUS_STYLE_PADRAO

// ── Regras de status (mesmas aplicadas pelo backend em app/services/operacoes.py) ──

export const STATUS_PRONTO = 'Pronto'

/** Pedido marcado por um operador como em análise: não é transmitido nem
 *  reprocessado, e fica fora de qualquer seleção em lote. */
export const STATUS_EM_ANALISE = 'Em Analise'

/** Gerações manuais aceitas para o pedido. A regra mora só na API
 *  (operacoes.acoes_de_geracao_manual: status, layout da indústria e, no
 *  cancelamento, pedido não faturado) — a tela não decide, só lê os campos. */
interface PedidoGeravel {
  pode_gerar_retorno?: boolean | null
  pode_gerar_espelho?: boolean | null
  pode_gerar_cancelamento?: boolean | null
}

export const podeGerarRetorno = (p: PedidoGeravel) => !!p.pode_gerar_retorno
export const podeGerarEspelho = (p: PedidoGeravel) => !!p.pode_gerar_espelho
export const podeGerarCancelamento = (p: PedidoGeravel) => !!p.pode_gerar_cancelamento
