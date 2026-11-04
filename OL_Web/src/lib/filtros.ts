/** Quantos filtros estão aplicados (ignora paginação) — badge do botão "Filtros". */
export function contarFiltrosAtivos(f: object): number {
  return Object.entries(f).filter(
    ([k, v]) => k !== 'page' && k !== 'size' && v !== undefined && v !== '' && v !== null,
  ).length
}
