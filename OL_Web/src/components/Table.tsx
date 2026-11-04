import type { ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { apiErr } from '../lib/apiError'

/**
 * Peças comuns das tabelas de listagem (F4 da auditoria).
 *
 * As colunas são declaradas uma vez (`Coluna[]`) e o número delas sai do
 * próprio array: o colSpan do estado vazio e do esqueleto deixa de ser escrito
 * à mão (estava errado em Confecção e Rastreamento). `TableFeedback` também
 * mostra o erro de carregamento, que antes aparecia como lista vazia (Q1).
 */

export interface Coluna {
  key: string
  label?: ReactNode
  align?: 'left' | 'center' | 'right'
  className?: string
}

const ALINHAMENTO = { left: 'text-left', center: 'text-center', right: 'text-right' }

export function Th({ align = 'left', className = '', children }: { align?: Coluna['align']; className?: string; children?: ReactNode }) {
  return (
    <th className={`${ALINHAMENTO[align]} px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide ${className}`}>
      {children}
    </th>
  )
}

export function TableHead({ colunas }: { colunas: Coluna[] }) {
  return (
    <thead>
      <tr className="border-b border-slate-200 bg-slate-50">
        {colunas.map((c) => (
          <Th key={c.key} align={c.align} className={c.className}>{c.label}</Th>
        ))}
      </tr>
    </thead>
  )
}

export function TableSkeleton({ colunas, linhas = 6 }: { colunas: number; linhas?: number }) {
  return (
    <>
      {Array.from({ length: linhas }).map((_, i) => (
        <tr key={i}>
          {Array.from({ length: colunas }).map((_, j) => (
            <td key={j} className="px-4 py-3">
              <div className="h-4 bg-slate-100 rounded animate-pulse" />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}

export function TableEmpty({ colunas, children }: { colunas: number; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={colunas} className="px-4 py-12 text-center text-slate-400 text-sm">{children}</td>
    </tr>
  )
}

export function TableError({ colunas, error, onRetry }: { colunas: number; error: unknown; onRetry?: () => void }) {
  return (
    <tr>
      <td colSpan={colunas} className="px-4 py-12 text-center text-sm">
        <div role="alert" className="inline-flex flex-col items-center gap-2 text-red-600">
          <span className="inline-flex items-center gap-2 font-medium">
            <AlertTriangle size={15} />
            {apiErr(error, 'Não foi possível carregar a lista. Verifique a conexão com o servidor.')}
          </span>
          {onRetry && (
            <button onClick={onRetry} className="text-xs text-slate-500 hover:text-slate-700 underline">
              Tentar novamente
            </button>
          )}
        </div>
      </td>
    </tr>
  )
}

/**
 * Linhas de estado da tabela: esqueleto, erro ou vazio. Devolve `null` quando
 * há dados — aí a tela renderiza as próprias linhas.
 */
export function TableFeedback({ colunas, isLoading, isError, error, onRetry, vazio, isEmpty, linhas }: {
  colunas: number
  isLoading: boolean
  isError?: boolean
  error?: unknown
  onRetry?: () => void
  isEmpty: boolean
  vazio: ReactNode
  linhas?: number
}) {
  if (isLoading) return <TableSkeleton colunas={colunas} linhas={linhas} />
  if (isError) return <TableError colunas={colunas} error={error} onRetry={onRetry} />
  if (isEmpty) return <TableEmpty colunas={colunas}>{vazio}</TableEmpty>
  return null
}
