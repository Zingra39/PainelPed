import { useEffect, useRef, type ReactNode } from 'react'

const FOCAVEIS =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Base acessível de todos os diálogos (Q5 da auditoria):
 * - `role="dialog"` + `aria-modal` + `aria-labelledby` apontando para o título;
 * - foco vai para dentro ao abrir (primeiro campo/botão, ou `autoFocus` de quem chamou)
 *   e volta para o elemento que abriu ao fechar;
 * - Tab e Shift+Tab ficam presos dentro do diálogo;
 * - Esc e clique fora fecham (exceto com `bloquearFechar`, ex.: durante um envio);
 *   formulários usam `fecharNoFundo={false}` para um clique fora não descartar o que foi digitado.
 */
export default function Modal({
  aberto, onFechar, tituloId, descricaoId, bloquearFechar = false, fecharNoFundo = true, className = 'max-w-sm rounded-xl shadow-lg', overlayClassName = 'bg-black/30', children,
}: {
  aberto: boolean
  onFechar: () => void
  /** id do elemento que dá nome ao diálogo (o título). */
  tituloId: string
  /** id do texto que descreve o diálogo, lido junto com o título. */
  descricaoId?: string
  bloquearFechar?: boolean
  fecharNoFundo?: boolean
  /** Largura, cantos, sombra e espaçamento do painel. */
  className?: string
  overlayClassName?: string
  children: ReactNode
}) {
  const painel = useRef<HTMLDivElement>(null)
  // Handler atual num ref: o efeito de foco só roda ao abrir/fechar, não a cada render.
  const fechar = useRef(onFechar)
  const bloqueado = useRef(bloquearFechar)
  useEffect(() => {
    fechar.current = onFechar
    bloqueado.current = bloquearFechar
  })

  useEffect(() => {
    if (!aberto) return
    const anterior = document.activeElement as HTMLElement | null
    const el = painel.current
    if (el && !el.contains(document.activeElement)) {
      const primeiro = el.querySelector<HTMLElement>(FOCAVEIS)
      ;(primeiro ?? el).focus()
    }

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && !bloqueado.current) {
        e.stopPropagation()
        fechar.current()
        return
      }
      if (e.key !== 'Tab' || !el) return
      const itens = [...el.querySelectorAll<HTMLElement>(FOCAVEIS)].filter((n) => n.offsetParent !== null)
      if (itens.length === 0) { e.preventDefault(); return }
      const primeiro = itens[0]
      const ultimo = itens[itens.length - 1]
      if (e.shiftKey && document.activeElement === primeiro) { e.preventDefault(); ultimo.focus() }
      else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primeiro.focus() }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      anterior?.focus?.()
    }
  }, [aberto])

  if (!aberto) return null

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 ${overlayClassName}`}
      onClick={() => { if (!bloquearFechar && fecharNoFundo) onFechar() }}
    >
      <div
        ref={painel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={tituloId}
        aria-describedby={descricaoId}
        tabIndex={-1}
        className={`bg-white w-full focus:outline-none ${className}`}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  )
}
