import { api } from './client'
import type { PaginatedResponse, OcorrenciaPedido } from '../types'

export interface OcorrenciasFilter {
  numero_pedido_ol?: string
  severidade?: string
  resolvido?: boolean
  page?: number
  size?: number
}

export const ocorrenciasApi = {
  list: (params: OcorrenciasFilter = {}) =>
    api.get<PaginatedResponse<OcorrenciaPedido>>('/ocorrencias', { params }).then((r) => r.data),
}
