import { api } from './client'
import type { Parametro, PendenciaConfiguracao } from '../types'

/** Chave do React Query do alerta global — invalidada ao salvar um parâmetro obrigatório. */
export const CHAVE_QUERY_PENDENCIAS = ['parametros-pendencias']

export interface UpdateParametro {
  valor: string
}

export const parametrosApi = {
  list: () => api.get<Parametro[]>('/parametros').then((r) => r.data),

  update: (chave: string, data: UpdateParametro) =>
    api.put<Parametro>(`/parametros/${chave}`, data).then((r) => r.data),

  /** Aberto a qualquer usuário logado — alimenta o alerta global do layout. */
  pendencias: () =>
    api.get<PendenciaConfiguracao[]>('/parametros/pendencias').then((r) => r.data),
}
