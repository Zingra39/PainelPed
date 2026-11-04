import { api } from './client'
import type { ErroItem } from '../types'

export const errosApi = {
  list: (descricao?: string) =>
    api.get<ErroItem[]>('/erros', { params: descricao ? { descricao } : {} }).then((r) => r.data),
}
