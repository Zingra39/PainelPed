import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'

/**
 * Formatação única de datas e valores da aplicação (F5 da auditoria).
 *
 * Antes havia um `fmtDate` em cada tela, e o mesmo nome produzia formatos
 * diferentes (só a data em umas, data e hora em outras). Aqui cada formato tem
 * um nome próprio:
 *   - `fmtData`          -> 31/12/2026
 *   - `fmtDataHora`      -> 31/12/2026 às 14:30   (textos, detalhes)
 *   - `fmtDataHoraCurta` -> 31/12/2026 14:30      (células de tabela)
 *
 * Valor ausente vira `vazio` (padrão "—"); data inválida devolve o texto
 * original, para o operador ao menos ver o que veio da API.
 */

type DataEntrada = string | null | undefined

function formatar(d: DataEntrada, padrao: string, vazio: string): string {
  if (!d) return vazio
  try { return format(new Date(d), padrao, { locale: ptBR }) } catch { return d }
}

export const fmtData = (d: DataEntrada, vazio = '—') => formatar(d, 'dd/MM/yyyy', vazio)
export const fmtDataHora = (d: DataEntrada, vazio = '—') => formatar(d, "dd/MM/yyyy 'às' HH:mm", vazio)
export const fmtDataHoraCurta = (d: DataEntrada, vazio = '—') => formatar(d, 'dd/MM/yyyy HH:mm', vazio)

type NumeroEntrada = number | string | null | undefined

function numero(v: NumeroEntrada): number | null {
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isNaN(n) ? null : n
}

export function fmtMoeda(v: NumeroEntrada): string {
  const n = numero(v)
  return n == null ? '—' : n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

export function fmtNumero(v: NumeroEntrada): string {
  const n = numero(v)
  return n == null ? '—' : n.toLocaleString('pt-BR')
}

export function fmtPct(v: NumeroEntrada): string {
  const n = numero(v)
  return n == null ? '—' : `${n.toFixed(2).replace('.', ',')}%`
}
