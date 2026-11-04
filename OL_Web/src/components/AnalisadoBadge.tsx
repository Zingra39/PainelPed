import { ClipboardCheck } from 'lucide-react'
import { fmtDataHora } from '../lib/format'
import Tooltip from './Tooltip'

interface AnalisadoBadgeProps {
  /** Nome de quem concluiu a análise (pedido.analisado_por). */
  por?: string | null
  /** Quando a análise foi concluída (pedido.analisado_em). Sem isso o selo não aparece. */
  em?: string | null
  size?: 'sm' | 'md'
}


/**
 * Selo "Analisado": mostra que um operador já analisou o pedido (fluxo "Em
 * Analise") e, no tooltip, quem e quando. Persiste depois que a análise acaba —
 * é o rastro que avisa os demais usuários de que o pedido já passou por olho
 * humano. Mostra sempre a ÚLTIMA análise; o histórico completo fica em
 * pedido_historico. Cor própria (verde-água) para não se confundir com o roxo
 * do status "Em Analise".
 */
export default function AnalisadoBadge({ por, em, size = 'sm' }: AnalisadoBadgeProps) {
  if (!em) return null

  const label = `Analisado${por ? ` por ${por}` : ''} em ${fmtDataHora(em)}`
  const sizeClass = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'

  return (
    <Tooltip label={label}>
      <span
        className={`inline-flex items-center gap-1 rounded-full border border-teal-200 bg-teal-50 font-medium text-teal-700 ${sizeClass}`}
      >
        <ClipboardCheck size={size === 'sm' ? 11 : 13} aria-hidden="true" />
        Analisado
      </span>
    </Tooltip>
  )
}
