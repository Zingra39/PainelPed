import { useState } from 'react'
import { contarFiltrosAtivos } from '../lib/filtros'
import type { FiltroTexto } from '../components/FilterBar'

/** Campos que a FilterBar edita (pesquisa e período) — comuns às listas de pedidos. */
interface FiltroBase extends FiltroTexto {
  page?: number
  size?: number
}

/**
 * Liga os filtros de uma listagem à FilterBar (F9 da auditoria).
 *
 * - Pesquisa e período: o rascunho fica dentro da FilterBar (R1) e só chega
 *   aqui no "Pesquisar".
 * - Os selects de cada tela aplicam na hora (`aplicar`), voltando à página 1.
 * - "Limpar" volta aos filtros iniciais.
 * A seção fica aberta: aplicar/limpar não a recolhe — só o botão "Filtros".
 */
export function useListFilters<F extends FiltroBase>(inicial: F) {
  const [filters, setFilters] = useState<F>(inicial)
  const [aberto, setAberto] = useState(true)
  const ativos = contarFiltrosAtivos(filters)

  return {
    filters,
    /** Aplica na hora um filtro próprio da tela (ex.: select de status). */
    aplicar: (patch: Partial<F>) => setFilters((f) => ({ ...f, ...patch, page: 1 })),
    setPage: (page: number) => setFilters((f) => ({ ...f, page })),
    toggleProps: { open: aberto, ativos, onClick: () => setAberto((v) => !v) },
    barProps: {
      open: aberto,
      aplicados: { busca: filters.busca, data_inicio: filters.data_inicio, data_fim: filters.data_fim },
      onSubmit: (v: FiltroTexto) => setFilters((f) => ({
        ...f,
        busca: v.busca?.trim() || undefined,
        data_inicio: v.data_inicio,
        data_fim: v.data_fim,
        page: 1,
      })),
      onClear: () => setFilters(inicial),
    },
  }
}
