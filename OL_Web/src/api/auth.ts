import { api } from './client'
import type { AuthUser, TokenResponse } from '../types'

export const authApi = {
  login: (email: string, senha: string) =>
    api.post<TokenResponse>('/auth/login', { email, senha }).then((r) => r.data),

  me: () => api.get<AuthUser>('/auth/me').then((r) => r.data),

  refresh: (refresh_token: string) =>
    api.post<TokenResponse>('/auth/refresh', { refresh_token }).then((r) => r.data),
}
