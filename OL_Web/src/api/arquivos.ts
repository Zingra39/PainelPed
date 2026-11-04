import { api } from './client'
import { baixarBlob } from '../lib/blob'
import type { Arquivo, PaginatedResponse } from '../types'

export interface ArquivosFilter {
  numero_pedido_ol?: string
  nome?: string
  tipo?: string
  situacao?: string
  page?: number
  size?: number
}

export const arquivosApi = {
  list: (params: ArquivosFilter = {}) =>
    api.get<PaginatedResponse<Arquivo>>('/arquivos', { params }).then((r) => r.data),

  download: async (id: number, nome: string): Promise<void> => {
    const response = await api.get<Blob>(`/arquivos/${id}/download`, {
      responseType: 'blob',
    })
    baixarBlob(response.data, nome)
  },
}
