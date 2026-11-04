import type { ReactNode } from 'react'
import { BRAND, NAVY } from '../../lib/cores'
import type { LucideIcon } from 'lucide-react'
import { AlertTriangle, Inbox } from 'lucide-react'

interface ChartCardProps {
  titulo: string
  subtitulo?: string
  altura?: number
  rodape?: ReactNode
  children: ReactNode
  /** Ícone exibido em um badge à esquerda do título, dando identidade visual
   * ao painel (mesma linguagem dos cards de KPI). Opcional. */
  icone?: LucideIcon
  /** Cor (hex) do badge do ícone e do acento visual do card. */
  cor?: string
}

/** Converte um hex em rgba() para usar como fundo translúcido do badge do ícone. */
function hexToRgba(hex: string, alpha: number) {
  const clean = hex.replace('#', '')
  const bigint = parseInt(clean, 16)
  const r = (bigint >> 16) & 255
  const g = (bigint >> 8) & 255
  const b = bigint & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/** Moldura padrão usada por todos os gráficos do Dashboard — mantém o
 * mesmo cartão (fundo branco, borda sutil, cantos arredondados) já usado
 * nos cards de KPI no topo da página, com um leve destaque de marca ao
 * passar o mouse (barra de gradiente navy → laranja no topo) e um badge
 * de ícone colorido que dá identidade visual imediata a cada painel. */
export default function ChartCard({
  titulo, subtitulo, altura = 280, rodape, children, icone: Icone, cor = NAVY,
}: ChartCardProps) {
  return (
    <div className="group relative bg-white rounded-2xl shadow-sm border border-slate-200/70 p-4 sm:p-5 hover:shadow-md transition-shadow duration-200 overflow-hidden">
      <span
        className="absolute inset-x-0 top-0 h-[3px] opacity-0 group-hover:opacity-100 transition-opacity duration-200"
        style={{ background: `linear-gradient(90deg, ${NAVY} 0%, ${BRAND} 100%)` }}
        aria-hidden="true"
      />
      <div className="flex items-start gap-3">
        {Icone && (
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: hexToRgba(cor, 0.12) }}
          >
            <Icone size={15} style={{ color: cor }} />
          </div>
        )}
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-slate-800">{titulo}</h2>
          {subtitulo && <p className="text-xs text-slate-500 mt-0.5">{subtitulo}</p>}
        </div>
      </div>
      <div style={{ height: altura }} className="mt-4">
        {children}
      </div>
      {rodape && <div className="mt-2 pt-2 border-t border-slate-100 text-xs text-slate-400">{rodape}</div>}
    </div>
  )
}

/** Falha ao carregar o gráfico (Q1 da auditoria): antes caía no estado vazio e
 *  dizia "nenhum dado no período", o que era falso. */
export function GraficoErro({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="h-full flex flex-col items-center justify-center text-center px-4 gap-2.5">
      <div className="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center">
        <AlertTriangle size={18} className="text-red-400" />
      </div>
      <p className="text-sm text-red-600">Não foi possível carregar este gráfico.</p>
      <button onClick={onRetry} className="text-xs text-slate-500 hover:text-slate-700 underline">
        Tentar novamente
      </button>
    </div>
  )
}

/** Estado vazio consistente para quando a consulta não retorna nenhum dado. */
export function GraficoVazio({ mensagem, icone: Icone = Inbox }: { mensagem: string; icone?: LucideIcon }) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center px-4 gap-2.5">
      <div className="w-10 h-10 rounded-full bg-slate-50 flex items-center justify-center">
        <Icone size={18} className="text-slate-300" />
      </div>
      <p className="text-sm text-slate-400">{mensagem}</p>
    </div>
  )
}
