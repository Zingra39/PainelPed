import { keepPreviousData } from '@tanstack/react-query'

/**
 * Estilos comuns dos gráficos do Dashboard (R5 da auditoria). Os quatro
 * gráficos repetiam os mesmos objetos inline em cada render; ficam aqui como
 * constantes de módulo, com uma única definição visual.
 */

export const GRID_STROKE = '#f1f5f9'
export const GRID_DASH = '3 6'

export const TICK_EIXO = { fill: '#94a3b8', fontSize: 11 }
export const TICK_CATEGORIA = { fill: '#334155', fontSize: 12 }

export const TOOLTIP_CONTENT = {
  borderRadius: 10, border: 'none', boxShadow: '0 4px 16px rgba(15,23,42,0.12)', fontSize: 12,
}
export const TOOLTIP_LABEL = { color: '#1e293b', fontWeight: 600 }
export const TOOLTIP_CURSOR_BARRA = { fill: '#f8fafc' }
export const TOOLTIP_CURSOR_LINHA = { stroke: '#cbd5e1', strokeWidth: 1 }

export const ROTULO_BARRA = { fill: '#475569', fontSize: 11, fontWeight: 600 }

export const RAIO_BARRA_HORIZONTAL: [number, number, number, number] = [0, 6, 6, 0]

/**
 * Opções de consulta de todos os painéis do Dashboard (R6 da auditoria): a
 * tela diz "tempo real", então atualiza sozinha a cada minuto e ao voltar o
 * foco para a aba, sem piscar o gráfico durante a troca de período. Para de
 * consultar enquanto a última tentativa estiver em erro (o botão de foco e a
 * troca de período tentam de novo). Vale até o tempo real por eventos
 * (seção 5 da auditoria) substituir o polling.
 */
export const DASHBOARD_POLLING_MS = 60_000

export const opcoesDashboard = {
  refetchInterval: (q: { state: { status: string } }) => (q.state.status === 'error' ? false : DASHBOARD_POLLING_MS),
  refetchOnWindowFocus: true,
  placeholderData: keepPreviousData,
} as const
