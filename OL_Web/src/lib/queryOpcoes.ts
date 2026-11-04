import { keepPreviousData } from '@tanstack/react-query'

/**
 * Opções comuns das consultas de listagem paginada (R2 da auditoria).
 *
 * - `placeholderData: keepPreviousData`: ao trocar de página ou de filtro, a
 *   tabela continua mostrando as linhas anteriores (esmaecidas pela tela via
 *   `isPlaceholderData`) em vez de voltar ao esqueleto a cada clique.
 * - Polling opcional que para enquanto a última tentativa estiver em erro —
 *   não adianta martelar um servidor fora do ar a cada 15 s; o botão
 *   "Atualizar" e a troca de filtro tentam de novo.
 */
export function opcoesLista(pollingMs?: number) {
  return {
    placeholderData: keepPreviousData,
    refetchInterval: (q: { state: { status: string } }) =>
      pollingMs && q.state.status !== 'error' ? pollingMs : false,
  } as const
}
