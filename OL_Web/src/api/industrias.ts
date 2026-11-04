import { api } from './client'
import type { Industria, IndustriaFornecedor, IndustriaFtp, IndustriaListItem } from '../types'

export interface IndustriaCreate {
  nome: string
  cnpj?: string
  layout?: string
  id_bbs?: number
  cond_mae?: number
  ativo?: boolean

  pasta_envio?: string
  pasta_entrada?: string
  pasta_retorno?: string
  pasta_espelho?: string
  pasta_cancelamento?: string
  pasta_backup_pedido?: string
  pasta_retorno_envio?: string
  pasta_retorno_espelho?: string
  pasta_pedido_original?: string
  pasta_envio_cancelamento?: string
  pasta_estoque?: string

  ftp?: Partial<IndustriaFtp>
  /** Lista completa: substitui a cadastrada. Omitir = não altera. */
  fornecedores?: IndustriaFornecedor[]
}

export type IndustriaUpdate = Partial<IndustriaCreate>

export interface IndustriasFilter {
  ativo?: boolean
}

export const industriasApi = {
  list: (params: IndustriasFilter = {}) =>
    api.get<IndustriaListItem[]>('/industrias', { params }).then((r) => r.data),

  get: (id: number) => api.get<Industria>(`/industrias/${id}`).then((r) => r.data),

  create: (data: IndustriaCreate) =>
    api.post<Industria>('/industrias', data).then((r) => r.data),

  update: (id: number, data: IndustriaUpdate) =>
    api.put<Industria>(`/industrias/${id}`, data).then((r) => r.data),

  remove: (id: number) => api.delete(`/industrias/${id}`),
}
