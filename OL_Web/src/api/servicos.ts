import { api } from './client'
import type { Servico } from '../types'

export const servicosApi = {
  list: () => api.get<Servico[]>('/servicos').then((r) => r.data),
  executar: (nome: string) =>
    api.post<{ mensagem: string }>(`/servicos/${nome}/executar`).then((r) => r.data),
}
