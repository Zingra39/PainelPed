import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Loader2 } from 'lucide-react'
import Tooltip from './Tooltip'

/**
 * Botões padrão do painel (F8 da auditoria). A cor da marca vem do token
 * `--color-brand` (`bg-brand`, ver index.css), não mais de `#285BBC` escrito
 * à mão em cada tela.
 */

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'
type ButtonSize = 'xs' | 'sm' | 'md'

const VARIANTES: Record<ButtonVariant, string> = {
  primary:   'bg-brand text-white font-medium shadow-sm hover:bg-brand-dark',
  secondary: 'border border-slate-300 bg-white text-slate-600 hover:bg-slate-50',
  danger:    'border border-red-200 bg-red-50 text-red-600 hover:bg-red-100',
  ghost:     'text-slate-500 hover:text-slate-700',
}

// Sem `className` que repita espaçamento: duas classes do mesmo utilitário
// (ex.: px-3 e px-4) não têm ordem garantida no CSS do Tailwind.
const TAMANHOS: Record<ButtonSize, string> = {
  xs: 'gap-1 px-2.5 py-1.5 text-xs',
  sm: 'gap-1.5 px-3 py-1.5 text-sm',
  md: 'gap-2 px-3 py-2 text-sm',
}

const ICONE_TAMANHO: Record<ButtonSize, number> = { xs: 12, sm: 13, md: 15 }

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  /** Troca o ícone por um spinner e desabilita o botão. */
  loading?: boolean
  icon?: ReactNode
}

export function Button({
  variant = 'secondary', size = 'md', loading = false, icon, disabled, className = '', children, type = 'button', ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex items-center justify-center rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${VARIANTES[variant]} ${TAMANHOS[size]} ${className}`}
      {...rest}
    >
      {loading ? <Loader2 size={ICONE_TAMANHO[size]} className="animate-spin" /> : icon}
      {children}
    </button>
  )
}

interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> {
  /** Obrigatório: vira o `aria-label` e o tooltip — botão só com ícone precisa de nome acessível. */
  label: string
  /** Tooltip diferente do nome acessível (ex.: explicar por que está desabilitado). */
  tooltip?: string
  loading?: boolean
  /** `outline` é o botão com borda do cabeçalho (ex.: atualizar); `row` é a ação compacta da linha da tabela. */
  appearance?: 'outline' | 'row'
  children: ReactNode
}

export function IconButton({
  label, tooltip, loading = false, appearance = 'row', disabled, className = '', children, type = 'button', ...rest
}: IconButtonProps) {
  const base = appearance === 'outline'
    ? 'p-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-500'
    : 'p-1.5 rounded text-slate-400'
  return (
    <Tooltip label={tooltip ?? label}>
      <button
        type={type}
        aria-label={label}
        disabled={disabled || loading}
        className={`${base} transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${className}`}
        {...rest}
      >
        {loading ? <Loader2 size={14} className="animate-spin" /> : children}
      </button>
    </Tooltip>
  )
}
