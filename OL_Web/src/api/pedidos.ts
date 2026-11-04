import { api } from './client'
import { baixarBlob } from '../lib/blob'
import type {
  LotePreview, LoteResultado, OperacaoResponse, PaginatedResponse, PaginatedConfeccao, PedidoDetalheCompleto,
  PedidoDetail, PedidoListItem, PedidoRastreamentoItem,
} from '../types'

export interface PedidosFilter {
  numero_pedido_ol?: string
  cnpj_cliente?: string
  status_operacional?: string
  status_erp?: string
  industria?: string
  data_inicio?: string
  data_fim?: string
  page?: number
  size?: number
}

export interface ConfeccaoFilter {
  /** Palavras-chave: nº do pedido, CNPJ, nome do arquivo ou indústria. */
  busca?: string
  numero_pedido_ol?: string
  cnpj_cliente?: string
  nome_arquivo?: string
  status_operacional?: string
  /** true = só pedidos já analisados; false = só os nunca analisados; ausente = todos. */
  analisado?: boolean
  data_inicio?: string
  data_fim?: string
  page?: number
  size?: number
}

export interface RastreamentoFilter {
  /** Palavras-chave: nº do pedido, CNPJ, nome do arquivo ou indústria. */
  busca?: string
  numero_pedido_ol?: string
  cnpj_cliente?: string
  nome_arquivo?: string
  status?: string
  data_inicio?: string
  data_fim?: string
  page?: number
  size?: number
}

export interface HistoricoFilter {
  /** Palavras-chave: nº do pedido, CNPJ, nome do arquivo ou indústria. */
  busca?: string
  numero_pedido_ol?: string
  cnpj_cliente?: string
  nome_arquivo?: string
  industria_nome?: string
  // "Pedido Concluido" | "Pedido Cancelado" — ver TipoStatusErp (OL_CORE)
  status_erp?: string
  data_inicio?: string
  data_fim?: string
  page?: number
  size?: number
}

export interface LotePeriodoFilter {
  data_inicio?: string
  data_fim?: string
  cnpj_cliente?: string
}

export interface ReprocessarLoteFilter {
  data_inicio?: string
  data_fim?: string
  cnpj_cliente?: string
  apenas_erro?: boolean
}

/** Reenvio é sempre de UM tipo — não existe "todos" nem no backend. */
export type TipoReenvioArquivo = 'retorno' | 'espelho' | 'cancelamento'

/** Export do Histórico: período obrigatório (o backend recusa sem ele). */
export interface HistoricoExportFilter extends Omit<HistoricoFilter, 'page' | 'size' | 'data_inicio' | 'data_fim'> {
  data_inicio: string
  data_fim: string
}

export interface ReenvioPeriodo {
  data_inicio?: string
  data_fim?: string
  industria_nome?: string
  status_erp?: string
}

export interface ReenvioPreview {
  total: number
  /** Teto vigente, vindo do parâmetro `limitador_de_envio`. */
  limite: number
  excede: boolean
}

export const pedidosApi = {
  list: (params: PedidosFilter = {}) =>
    api.get<PaginatedResponse<PedidoListItem>>('/pedidos', { params }).then((r) => r.data),

  confeccaoList: (params: ConfeccaoFilter = {}) =>
    api.get<PaginatedConfeccao>('/pedidos/confeccao', { params }).then((r) => r.data),

  rastreamentoList: (params: RastreamentoFilter = {}) =>
    api.get<PaginatedResponse<PedidoRastreamentoItem>>('/pedidos/rastreamento', { params }).then((r) => r.data),

  historicoList: (params: HistoricoFilter = {}) =>
    api.get<PaginatedResponse<PedidoRastreamentoItem>>('/pedidos/historico', { params }).then((r) => r.data),

  get: (id: number) =>
    api.get<PedidoDetail>(`/pedidos/${id}`).then((r) => r.data),

  getDetalhes: (id: number) =>
    api.get<PedidoDetalheCompleto>(`/pedidos/${id}/detalhes`).then((r) => r.data),

  gerarRetorno: (id: number) =>
    api.post<OperacaoResponse>(`/pedidos/${id}/retorno`).then((r) => r.data),

  gerarEspelho: (id: number) =>
    api.post<OperacaoResponse>(`/pedidos/${id}/espelho`).then((r) => r.data),

  reprocessar: (id: number) =>
    api.post<OperacaoResponse>(`/pedidos/${id}/reprocessar`).then((r) => r.data),

  // Reenvio: entrega de novo o MESMO arquivo já gerado (o backend lê o
  // caminho gravado em `arquivo`), sem regerar conteúdo nem mexer no status.
  reenviarLote: (ids: number[], tipo: TipoReenvioArquivo) =>
    api.post<LoteResultado>('/pedidos/lote/reenviar', { ids, tipo }).then((r) => r.data),

  // Reenvio por período: mesmo recorte da listagem do Histórico (resolvido no
  // backend pelo MESMO filtro), mas de um tipo de arquivo por disparo — nunca
  // os três juntos.
  reenviarPeriodo: (p: ReenvioPeriodo, tipo: TipoReenvioArquivo) =>
    api.post<LoteResultado>('/pedidos/lote/reenviar', { ...p, tipo }).then((r) => r.data),

  // Conta antes de disparar: reenvio mexe em pasta de indústria e FTP, então
  // o operador confirma sabendo o volume — e o teto (parâmetro
  // `limitador_de_envio`) vem junto para a tela dizer qual limite foi estourado.
  // A contagem é por tipo: pedido sem cancelamento não entra no total de um
  // reenvio de cancelamento.
  previewReenvio: (p: ReenvioPeriodo, tipo: TipoReenvioArquivo) =>
    api.get<ReenvioPreview>('/pedidos/lote/reenviar/preview', { params: { ...p, tipo } }).then((r) => r.data),

  transmitir: (id: number) =>
    api.post<OperacaoResponse>(`/pedidos/${id}/transmitir`).then((r) => r.data),

  // "Em Analise": marca o pedido como em análise por quem está logado (409 se
  // outro operador chegou primeiro).
  iniciarAnalise: (id: number) =>
    api.post<OperacaoResponse>(`/pedidos/${id}/analise`).then((r) => r.data),

  // Encerra a análise: o backend reprocessa o pedido e o devolve como
  // Pronto/Verificar. Se o reprocessamento falhar, responde erro e o pedido
  // continua em análise.
  encerrarAnalise: (id: number) =>
    api.delete<OperacaoResponse>(`/pedidos/${id}/analise`).then((r) => r.data),

  // O nome do autor é prefixado pelo backend (vem do token), então aqui vai
  // só o texto digitado.
  salvarObservacao: (id: number, observacao: string) =>
    api.patch<OperacaoResponse>(`/pedidos/${id}/observacao`, { observacao }).then((r) => r.data),

  cancelar: (id: number) =>
    api.post<OperacaoResponse>(`/pedidos/${id}/cancelamento`).then((r) => r.data),

  reprocessarLoteNaoTransmitidos: (params: ReprocessarLoteFilter = {}) =>
    api.post<LoteResultado>('/pedidos/lote/reprocessar', params).then((r) => r.data),

  loteRetorno: (params: LotePeriodoFilter) =>
    api.post<LoteResultado>('/pedidos/lote/retorno', params).then((r) => r.data),

  loteEspelho: (params: LotePeriodoFilter) =>
    api.post<LoteResultado>('/pedidos/lote/espelho', params).then((r) => r.data),

  loteCancelamento: (params: LotePeriodoFilter) =>
    api.post<LoteResultado>('/pedidos/lote/cancelamento', params).then((r) => r.data),

  loteTransmitir: (params: { apenas_sem_ocorrencia: boolean }) =>
    api.post<LoteResultado>('/pedidos/lote/transmitir', params).then((r) => r.data),

  // Prévias (somente leitura) — contam quantos pedidos cada ação em lote
  // afetaria, sem executar nada. Usadas pela tela de confirmação antes do
  // disparo real; o filtro é idêntico ao aplicado pela rota de execução.
  previewReprocessarLote: (params: ReprocessarLoteFilter = {}) =>
    api.get<LotePreview>('/pedidos/lote/reprocessar/preview', { params }).then((r) => r.data),

  previewLoteRetorno: (params: LotePeriodoFilter = {}) =>
    api.get<LotePreview>('/pedidos/lote/retorno/preview', { params }).then((r) => r.data),

  previewLoteEspelho: (params: LotePeriodoFilter = {}) =>
    api.get<LotePreview>('/pedidos/lote/espelho/preview', { params }).then((r) => r.data),

  previewLoteCancelamento: (params: LotePeriodoFilter = {}) =>
    api.get<LotePreview>('/pedidos/lote/cancelamento/preview', { params }).then((r) => r.data),

  previewLoteTransmitir: (params: { apenas_sem_ocorrencia: boolean }) =>
    api.get<LotePreview>('/pedidos/lote/transmitir/preview', { params }).then((r) => r.data),

  // Card #42 — o backend sinaliza no header X-Arquivo-Origem se o download é
  // o arquivo original (em disco) ou uma reconstrução a partir do banco.
  gerarPedido: async (id: number, nomeArquivo: string): Promise<'original' | 'reconstruido' | null> => {
    const response = await api.get<Blob>(`/pedidos/${id}/gerar-pedido`, {
      responseType: 'blob',
    })
    baixarBlob(response.data, nomeArquivo)
    const origem = response.headers['x-arquivo-origem']
    return origem === 'reconstruido' || origem === 'original' ? origem : null
  },

  exportConfeccao: (params: ConfeccaoFilter = {}) =>
    exportar('/pedidos/confeccao/export', params, 'confeccao.xlsx'),

  exportRastreamento: (params: RastreamentoFilter = {}) =>
    exportar('/pedidos/rastreamento/export', params, 'rastreamento.xlsx'),

  // Diferente dos outros dois exports: o período é obrigatório no tipo porque
  // é obrigatório no backend — o Histórico acumula tudo que já encerrou, e um
  // export sem recorte cresce sem teto.
  exportHistorico: (params: HistoricoExportFilter) =>
    exportar('/pedidos/historico/export', params, 'historico.xlsx'),
}

/**
 * Baixa uma planilha de export (F10 da auditoria). `page`/`size` são
 * descartados de propósito: o export devolve tudo, não paginado.
 *
 * Em erro o corpo chega como Blob — trate com `apiErrBlob` (lib/apiError) para
 * mostrar o motivo real do backend.
 */
async function exportar(url: string, params: object, nomeArquivo: string): Promise<void> {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { page: _page, size: _size, ...filtros } = params as { page?: number; size?: number }
  const response = await api.get<Blob>(url, { params: filtros, responseType: 'blob' })
  baixarBlob(response.data, nomeArquivo)
}
