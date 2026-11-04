import { AlertTriangle } from 'lucide-react'
import { apiErr } from '../lib/apiError'

/**
 * Aviso de falha ao carregar dados de uma tela (Q1 da auditoria). Substitui o
 * comportamento antigo de mostrar zeros, lista vazia ou controles com valor
 * padrão — que o operador lia como dado real.
 */
export default function ErroCarregamento({ titulo, error, onRetry }: {
  titulo: string
  error?: unknown
  onRetry: () => void
}) {
  const detalhe = error ? apiErr(error, '') : ''
  return (
    <div role="alert" className="mb-4 flex items-center gap-3 px-4 py-3 rounded-lg border border-red-200 bg-red-50 text-sm text-red-700">
      <AlertTriangle size={15} className="shrink-0" />
      <span>
        <span className="font-medium">{titulo}</span>
        {detalhe && <span className="text-red-600"> {detalhe}</span>}
      </span>
      <button onClick={onRetry} className="ml-auto shrink-0 text-xs text-red-600 hover:text-red-800 underline">
        Tentar novamente
      </button>
    </div>
  )
}
