import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8080'

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Promise compartilhada do refresh em andamento (task #35 — Azure Boards).
//
// Antes, um booleano simples (`refreshing`) controlava o fluxo: só a
// PRIMEIRA requisição que tomasse 401 entrava no `if` e disparava o refresh;
// qualquer outra que chegasse enquanto o refresh estava em andamento via
// `!refreshing` como `false` e era rejeitada na hora — mesmo que o token
// estivesse prestes a ser renovado com sucesso. Isso é comum no Dashboard,
// que dispara várias chamadas em paralelo (cards + 4 gráficos): ao expirar o
// token, só uma delas se recuperava e as demais quebravam a tela.
//
// Agora, todas as requisições que chegam durante um refresh em andamento
// aguardam essa MESMA promise em vez de cada uma tentar (ou desistir) por
// conta própria. Resultado: N requisições concorrentes → uma única chamada
// a /auth/refresh, e todas se recuperam com o token novo.
let refreshPromise: Promise<string> | null = null

function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const refresh = localStorage.getItem('refresh_token')
      if (!refresh) throw new Error('no refresh token')
      const { data } = await axios.post(`${BASE_URL}/auth/refresh`, {
        refresh_token: refresh,
      })
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      return data.access_token as string
    })()
      .catch((err) => {
        // Sessão realmente expirou (ou não há refresh_token) — limpa tudo e
        // manda pro login uma única vez, mesmo com N requisições concorrentes
        // aguardando essa mesma promise (evita N redirecionamentos/limpezas).
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
        throw err
      })
      .finally(() => {
        // Libera o slot para o PRÓXIMO ciclo de expiração disparar um novo refresh.
        refreshPromise = null
      })
  }
  return refreshPromise
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      try {
        const novoToken = await refreshAccessToken()
        original.headers.Authorization = `Bearer ${novoToken}`
        return api(original)
      } catch {
        return Promise.reject(error)
      }
    }
    return Promise.reject(error)
  },
)
