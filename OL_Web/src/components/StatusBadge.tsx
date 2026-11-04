import { exibirStatus } from '../lib/statusEnum'
import { estiloStatus } from '../lib/statusConfig'

interface StatusBadgeProps {
  /** Status vazio mostra um traço — útil em colunas opcionais (ex.: arquivo ainda não gerado). */
  status: string | null | undefined
  size?: 'sm' | 'md'
}

export default function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  if (!status) return <span className="text-slate-300 text-xs">—</span>

  const sizeClass = size === 'sm'
    ? 'px-2 py-0.5 text-xs'
    : 'px-2.5 py-1 text-sm'

  return (
    <span className={`inline-flex items-center font-medium rounded-full whitespace-nowrap ${estiloStatus(status)} ${sizeClass}`}>
      {exibirStatus(status)}
    </span>
  )
}
