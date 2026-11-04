import { createContext, useContext, useState, useEffect, useCallback, useMemo, type ReactNode } from 'react'
import { authApi } from '../api/auth'
import { perfilEmAlgum, perfilEquivalente } from '../lib/perfil'
import type { AuthUser } from '../types'

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  login: (email: string, senha: string) => Promise<void>
  logout: () => void
  isAdmin: boolean
  isOperacional: boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem('access_token')
    if (!token) { setLoading(false); return }
    try {
      const me = await authApi.me()
      setUser(me)
    } catch (err: unknown) {
      // only clear tokens on 401 (token invalid/expired); ignore network/server errors
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 401) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadUser() }, [loadUser])

  const login = useCallback(async (email: string, senha: string) => {
    const tokens = await authApi.login(email, senha)
    localStorage.setItem('access_token', tokens.access_token)
    localStorage.setItem('refresh_token', tokens.refresh_token)
    const me = await authApi.me()
    setUser(me)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setUser(null)
  }, [])

  // Valor memoizado (R4 da auditoria): sem isso, cada render do provider
  // criava um objeto novo e redesenhava todos os consumidores de useAuth.
  // Comparação tolerante (acento/caixa/dano de charset no nome gravado no
  // banco) — mesmas regras do require_perfis no backend, ver lib/perfil.ts.
  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    login,
    logout,
    isAdmin: perfilEquivalente(user?.perfil, 'Administrador'),
    isOperacional: perfilEmAlgum(user?.perfil, ['Administrador', 'Operador Logístico']),
  }), [user, loading, login, logout])

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
