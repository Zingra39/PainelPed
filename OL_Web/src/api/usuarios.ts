import { api } from './client'
import type { Perfil, PaginatedResponse, Usuario } from '../types'

export interface CreateUsuario {
  nome: string
  email: string
  senha: string
  id_perfil: number
}

export interface UpdateUsuario {
  nome?: string
  email?: string
  senha?: string
  id_perfil?: number
  ativo?: boolean
}

export interface UsuariosFilter {
  nome?: string
  id_perfil?: number
  ativo?: boolean
  page?: number
  size?: number
}

export const usuariosApi = {
  list: (params: UsuariosFilter = {}) =>
    api.get<PaginatedResponse<Usuario>>('/usuarios', { params }).then((r) => r.data),

  get: (id: number) => api.get<Usuario>(`/usuarios/${id}`).then((r) => r.data),

  create: (data: CreateUsuario) =>
    api.post<Usuario>('/usuarios', data).then((r) => r.data),

  update: (id: number, data: UpdateUsuario) =>
    api.put<Usuario>(`/usuarios/${id}`, data).then((r) => r.data),

  deactivate: (id: number) => api.delete(`/usuarios/${id}`),

  deletePermanent: (id: number) => api.delete(`/usuarios/${id}/permanente`),

  perfis: () => api.get<Perfil[]>('/usuarios/perfis').then((r) => r.data),
}
