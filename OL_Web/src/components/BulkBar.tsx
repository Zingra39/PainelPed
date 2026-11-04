import type { ReactNode } from 'react'

/** Barra de ações sobre as linhas selecionadas (F3 da auditoria). Some quando nada está selecionado. */
export default function BulkBar({ total, onLimpar, disabled, tom = 'blue', children }: {
  total: number
  onLimpar: () => void
  disabled?: boolean
  tom?: 'blue' | 'slate'
  children: ReactNode
}) {
  if (total === 0) return null
  const [fundo, texto] = tom === 'blue'
    ? ['bg-blue-50 border-blue-200', 'text-blue-700']
    : ['bg-slate-50 border-slate-200', 'text-slate-700']
  return (
    <div className={`mb-4 flex items-center gap-3 px-4 py-3 border rounded-xl text-sm flex-wrap ${fundo}`}>
      <span className={`font-medium ${texto}`}>{total} selecionado(s)</span>
      {children}
      <button
        onClick={onLimpar}
        disabled={disabled}
        className="ml-auto text-xs text-slate-500 hover:text-slate-700 disabled:opacity-50"
      >
        Limpar seleção
      </button>
    </div>
  )
}
