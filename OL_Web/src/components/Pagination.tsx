import { ChevronLeft, ChevronRight } from 'lucide-react'

interface PaginationProps {
  page: number
  pages: number
  total: number
  size: number
  onPageChange: (page: number) => void
}

const range = (start: number, end: number): number[] =>
  Array.from({ length: Math.max(end - start + 1, 0) }, (_, i) => start + i)

/**
 * Monta a lista de páginas a exibir com reticências.
 * Sempre mostra a primeira, a última e as vizinhas da página atual;
 * insere '…' onde houver vão. Mantém ~7 itens visíveis.
 */
function montarPaginas(current: number, total: number, siblings = 1): (number | 'dots')[] {
  const maxItens = siblings * 2 + 5 // primeira + última + atual + 2*vizinhas + 2 reticências
  if (total <= maxItens) return range(1, total)

  const vizinhaEsq = Math.max(current - siblings, 1)
  const vizinhaDir = Math.min(current + siblings, total)
  const mostrarDotsEsq = vizinhaEsq > 2
  const mostrarDotsDir = vizinhaDir < total - 1

  if (!mostrarDotsEsq && mostrarDotsDir) {
    return [...range(1, 3 + 2 * siblings), 'dots', total]
  }
  if (mostrarDotsEsq && !mostrarDotsDir) {
    return [1, 'dots', ...range(total - (2 + 2 * siblings), total)]
  }
  return [1, 'dots', ...range(vizinhaEsq, vizinhaDir), 'dots', total]
}

export default function Pagination({ page, pages, total, size, onPageChange }: PaginationProps) {
  const from = (page - 1) * size + 1
  const to = Math.min(page * size, total)
  const itens = montarPaginas(page, pages)

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200">
      <p className="text-sm text-slate-500">
        {total === 0 ? 'Nenhum registro' : `${from}–${to} de ${total}`}
      </p>
      <nav aria-label="Paginação" className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          aria-label="Página anterior"
          className="p-1.5 rounded hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft size={16} />
        </button>
        {itens.map((item, i) =>
          item === 'dots' ? (
            <span
              key={`dots-${i}`}
              className="w-8 h-8 flex items-center justify-center text-sm text-slate-400 select-none"
            >
              …
            </span>
          ) : (
            <button
              key={item}
              onClick={() => onPageChange(item)}
              aria-label={`Página ${item}`}
              className={`w-8 h-8 text-sm rounded transition-colors ${
                item === page
                  ? 'bg-brand text-white font-medium'
                  : 'hover:bg-slate-100 text-slate-600'
              }`}
              aria-current={item === page ? 'page' : undefined}
            >
              {item}
            </button>
          )
        )}
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= pages}
          aria-label="Próxima página"
          className="p-1.5 rounded hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRight size={16} />
        </button>
      </nav>
    </div>
  )
}
