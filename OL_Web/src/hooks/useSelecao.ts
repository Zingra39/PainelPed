import { useMemo, useState } from 'react'

const VAZIO: ReadonlySet<number> = new Set()

/**
 * Seleção de linhas de uma listagem paginada (F3 da auditoria).
 *
 * - `idsSelecionaveis`: ids da página atual que podem ser marcados. O que não
 *   está nessa lista nunca conta como selecionado — se um pedido some da
 *   página (mudou de status no polling), ele sai da seleção sozinho.
 * - `contexto`: qualquer valor que identifique a consulta (filtros + página).
 *   Quando muda, a seleção é descartada. Corrige o Q2 da auditoria: antes a
 *   seleção sobrevivia à troca de página e de filtro, e uma ação em lote
 *   mandava ids que o operador nem estava vendo.
 */
export function useSelecao(idsSelecionaveis: number[], contexto: unknown) {
  const chave = JSON.stringify(contexto)
  const [estado, setEstado] = useState<{ chave: string; ids: ReadonlySet<number> }>({ chave, ids: VAZIO })

  const brutos = estado.chave === chave ? estado.ids : VAZIO
  const permitidos = idsSelecionaveis.join(',')
  const selecionados = useMemo(() => {
    const ok = new Set(permitidos ? permitidos.split(',').map(Number) : [])
    return new Set([...brutos].filter((id) => ok.has(id)))
  }, [brutos, permitidos])

  const definir = (ids: Iterable<number>) => setEstado({ chave, ids: new Set(ids) })

  const todosMarcados = idsSelecionaveis.length > 0 && idsSelecionaveis.every((id) => selecionados.has(id))

  return {
    selecionados,
    ids: [...selecionados],
    total: selecionados.size,
    has: (id: number) => selecionados.has(id),
    alternar: (id: number) => {
      const next = new Set(selecionados)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      definir(next)
    },
    todosMarcados,
    alternarTodos: () => definir(todosMarcados ? [] : idsSelecionaveis),
    limpar: () => definir([]),
  }
}

export type Selecao = ReturnType<typeof useSelecao>
