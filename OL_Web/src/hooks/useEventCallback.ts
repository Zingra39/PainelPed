import { useCallback, useLayoutEffect, useRef } from 'react'

/**
 * Callback com identidade estável que sempre chama a versão mais recente de
 * `fn`. Serve para passar handlers a linhas de tabela com `memo` (R1 da
 * auditoria) sem que um handler recriado a cada render da página invalide o
 * memo de todas as linhas.
 *
 * Só para handlers de evento — não chame durante o render.
 */
export function useEventCallback<A extends unknown[], R>(fn: (...args: A) => R): (...args: A) => R {
  const ref = useRef(fn)
  useLayoutEffect(() => { ref.current = fn })
  return useCallback((...args: A) => ref.current(...args), [])
}
