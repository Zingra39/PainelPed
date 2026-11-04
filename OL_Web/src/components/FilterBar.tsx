import { useState, type ReactNode } from 'react'
import { Search, X, CalendarDays, SlidersHorizontal } from 'lucide-react'

// Seção única de filtros das listagens de pedidos (Triagem, Rastreamento,
// Histórico). Concentra num só cartão, no topo da lista:
//   - um campo de pesquisa por palavras-chave (o backend procura cada palavra
//     no nº do pedido, CNPJ, nome do arquivo e indústria — ver `_filtrar_busca`
//     em OL_API/app/routers/pedidos.py);
//   - o período (data início/fim) em formato compacto;
//   - os filtros próprios de cada tela (selects), passados como `children`.
// A pesquisa e o período são aplicados com Enter ou "Pesquisar"; os selects de
// cada tela continuam aplicando na hora.
//
// O rascunho da pesquisa e do período vive AQUI, não na página (R1 da
// auditoria): antes cada tecla atualizava o estado da página e redesenhava
// cabeçalho, painéis, diálogos e todas as linhas da tabela. Agora só este
// cartão redesenha enquanto o usuário digita; a página só fica sabendo no
// "Pesquisar".

export const inputFiltroClass =
  'h-9 px-3 rounded-lg border border-slate-300 bg-white text-sm text-slate-700 ' +
  'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors'

export interface FiltroTexto {
  busca?: string
  data_inicio?: string
  data_fim?: string
}

interface FilterBarProps {
  open: boolean
  /** Valores já aplicados na consulta — o rascunho recomeça deles quando mudam. */
  aplicados: FiltroTexto
  onSubmit: (valores: FiltroTexto) => void
  onClear: () => void
  /** Filtros específicos da tela (selects), renderizados ao lado do período. */
  children?: ReactNode
}

const chaveDe = (f: FiltroTexto) => `${f.busca ?? ''}|${f.data_inicio ?? ''}|${f.data_fim ?? ''}`

export default function FilterBar({ open, aplicados, onSubmit, onClear, children }: FilterBarProps) {
  const [draft, setDraft] = useState<FiltroTexto>(aplicados)
  // Os filtros aplicados mudaram por fora (pesquisa aplicada, "Limpar"):
  // o rascunho volta a refletir o que está valendo.
  const [chaveAplicada, setChaveAplicada] = useState(chaveDe(aplicados))
  if (chaveDe(aplicados) !== chaveAplicada) {
    setChaveAplicada(chaveDe(aplicados))
    setDraft(aplicados)
  }

  if (!open) return null

  const busca = draft.busca ?? ''
  const dataInicio = draft.data_inicio ?? ''
  const dataFim = draft.data_fim ?? ''
  const editar = (campo: keyof FiltroTexto) => (v: string) => setDraft((d) => ({ ...d, [campo]: v || undefined }))
  const onBuscaChange = editar('busca')
  const onDataInicioChange = editar('data_inicio')
  const onDataFimChange = editar('data_fim')

  const periodoInvalido = !!dataInicio && !!dataFim && dataFim < dataInicio

  return (
    <form
      className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4"
      onSubmit={(e) => { e.preventDefault(); if (!periodoInvalido) onSubmit(draft) }}
    >
      <div className="flex flex-wrap items-end gap-3">
        {/* Pesquisa por palavras-chave */}
        <div className="flex-1 min-w-[16rem]">
          <label htmlFor="filtro-busca" className="block text-xs font-medium text-slate-600 mb-1">
            Pesquisar
          </label>
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input
              id="filtro-busca"
              type="search"
              value={busca}
              onChange={(e) => onBuscaChange(e.target.value)}
              placeholder="Nº do pedido, CNPJ, nome do arquivo ou indústria…"
              autoComplete="off"
              className={`${inputFiltroClass} w-full pl-9 pr-8`}
            />
            {busca && (
              <button
                type="button"
                onClick={() => onBuscaChange('')}
                aria-label="Limpar pesquisa"
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100"
              >
                <X size={13} />
              </button>
            )}
          </div>
        </div>

        {/* Período compacto */}
        <div>
          <span className="flex items-center gap-1 text-xs font-medium text-slate-600 mb-1">
            <CalendarDays size={12} className="text-slate-400" />
            Período
          </span>
          <div className={`flex items-center h-9 rounded-lg border bg-white transition-colors focus-within:ring-2 focus-within:ring-blue-500 ${
            periodoInvalido ? 'border-red-400' : 'border-slate-300'
          }`}>
            <input
              type="date"
              aria-label="Data início"
              value={dataInicio}
              onChange={(e) => onDataInicioChange(e.target.value)}
              className="w-[8.25rem] h-full px-2 bg-transparent text-sm text-slate-700 rounded-l-lg focus:outline-none"
            />
            <span className="text-slate-300 text-xs px-0.5">até</span>
            <input
              type="date"
              aria-label="Data fim"
              value={dataFim}
              min={dataInicio || undefined}
              onChange={(e) => onDataFimChange(e.target.value)}
              className="w-[8.25rem] h-full px-2 bg-transparent text-sm text-slate-700 rounded-r-lg focus:outline-none"
            />
          </div>
        </div>

        {children}

        <div className="flex items-center gap-2">
          <button
            type="submit"
            disabled={periodoInvalido}
            className="flex items-center gap-2 h-9 px-4 bg-brand text-white text-sm font-medium rounded-lg transition-colors hover:bg-brand-dark disabled:opacity-50"
          >
            <Search size={14} /> Pesquisar
          </button>
          <button
            type="button"
            onClick={() => { setDraft({}); onClear() }}
            className="h-9 px-3 border border-slate-300 text-sm text-slate-600 rounded-lg hover:bg-slate-50 transition-colors"
          >
            Limpar
          </button>
        </div>
      </div>
      {periodoInvalido && (
        <p className="mt-2 text-xs text-red-600">A data final não pode ser anterior à inicial.</p>
      )}
    </form>
  )
}

/** Campo de filtro (select) com rótulo, no mesmo padrão visual do FilterBar. */
export function FiltroSelect({ label, value, onChange, children }: {
  label: string
  value: string
  onChange: (v: string) => void
  children: ReactNode
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-600 mb-1">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`${inputFiltroClass} pr-8 max-w-[14rem]`}
      >
        {children}
      </select>
    </div>
  )
}

/** Botão "Filtros" do cabeçalho: mostra/oculta a seção e indica quantos filtros estão ativos. */
export function FilterToggleButton({ open, ativos, onClick }: { open: boolean; ativos: number; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={open}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors ${
        open
          ? 'border-blue-400 bg-blue-50 text-blue-700'
          : 'border-slate-300 bg-white hover:bg-slate-50 text-slate-600'
      }`}
    >
      <SlidersHorizontal size={15} />
      Filtros
      {ativos > 0 && (
        <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-full text-[11px] font-semibold text-white bg-brand">
          {ativos}
        </span>
      )}
    </button>
  )
}
