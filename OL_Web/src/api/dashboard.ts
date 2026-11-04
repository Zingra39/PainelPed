import { api } from './client'
import type {
  ArquivosPorDiaItem,
  DashboardCards,
  MotivoCancelamentoItem,
  PedidosFaturadosPorDiaItem,
  PeriodoFiltro,
  TopProdutoItem,
} from '../types'

export const dashboardApi = {
  cards: (periodo: PeriodoFiltro) =>
    api.get<DashboardCards>('/dashboard/cards', { params: periodo }).then((r) => r.data),

  motivosCancelamento: (periodo: PeriodoFiltro) =>
    api
      .get<MotivoCancelamentoItem[]>('/dashboard/motivos-cancelamento', { params: periodo })
      .then((r) => r.data),

  arquivosEnviadosPorDia: (periodo: PeriodoFiltro) =>
    api
      .get<ArquivosPorDiaItem[]>('/dashboard/arquivos-enviados-por-dia', { params: periodo })
      .then((r) => r.data),

  pedidosFaturadosPorDia: (periodo: PeriodoFiltro) =>
    api
      .get<PedidosFaturadosPorDiaItem[]>('/dashboard/pedidos-faturados-por-dia', { params: periodo })
      .then((r) => r.data),

  topProdutos: (periodo: PeriodoFiltro, limite = 10) =>
    api
      .get<TopProdutoItem[]>('/dashboard/top-produtos', { params: { ...periodo, limite } })
      .then((r) => r.data),
}
