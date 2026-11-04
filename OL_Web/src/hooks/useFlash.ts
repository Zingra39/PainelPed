import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Mensagem temporária de feedback das telas (F1 da auditoria).
 *
 * Substitui o par `showMsg` + `setTimeout` que cada tela tinha. Aquele padrão
 * não limpava o timer anterior: uma segunda mensagem era apagada pelo timer da
 * primeira antes da hora, e o timer seguia vivo depois de a tela desmontar.
 * Aqui só existe um timer por vez, cancelado a cada nova mensagem e no unmount.
 */

export type FlashTipo = 'sucesso' | 'erro' | 'aviso'

export interface Flash {
  tipo: FlashTipo
  texto: string
  /** Permite exibir a mensagem junto de um item específico (ex.: o card de um serviço). */
  chave?: string | number
}

export interface UseFlash {
  flash: Flash | null
  mostrar: (tipo: FlashTipo, texto: string, opts?: { chave?: string | number; duracaoMs?: number }) => void
  sucesso: (texto: string) => void
  erro: (texto: string) => void
  limpar: () => void
}

export function useFlash(duracaoPadraoMs = 4000): UseFlash {
  const [flash, setFlash] = useState<Flash | null>(null)
  const timer = useRef<number | undefined>(undefined)

  const limpar = useCallback(() => {
    window.clearTimeout(timer.current)
    setFlash(null)
  }, [])

  const mostrar = useCallback<UseFlash['mostrar']>((tipo, texto, opts) => {
    window.clearTimeout(timer.current)
    setFlash({ tipo, texto, chave: opts?.chave })
    timer.current = window.setTimeout(() => setFlash(null), opts?.duracaoMs ?? duracaoPadraoMs)
  }, [duracaoPadraoMs])

  useEffect(() => () => window.clearTimeout(timer.current), [])

  const sucesso = useCallback((texto: string) => mostrar('sucesso', texto), [mostrar])
  const erro = useCallback((texto: string) => mostrar('erro', texto), [mostrar])

  return { flash, mostrar, sucesso, erro, limpar }
}
