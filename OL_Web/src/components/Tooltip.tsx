import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

interface TooltipProps {
  /** Texto do balão. Vazio/undefined desativa o tooltip — o filho é renderizado sozinho. */
  label?: string | null
  children: ReactNode
  /** Atraso em ms antes de aparecer, para não piscar quando o mouse só passa de raspão. */
  delay?: number
  /** Classes extras no wrapper (o elemento que "segura" o gatilho). */
  className?: string
}

const ESPACO = 8 // distância entre o gatilho e o balão
const MARGEM = 8 // respiro mínimo das bordas da janela

/**
 * Tooltip padrão do PainelOL — substitui o `title` nativo, que o navegador
 * renderiza com o visual do sistema operacional (sem controle de estilo,
 * atraso longo e fora da identidade do painel).
 *
 * Renderiza via portal no <body> com posição `fixed`: as tabelas do sistema
 * ficam dentro de containers com `overflow-hidden`, que recortariam um balão
 * posicionado de forma absoluta dentro da linha.
 *
 * Uso: <Tooltip label="Editar"><button …/></Tooltip>
 */
export default function Tooltip({ label, children, delay = 120, className }: TooltipProps) {
  const gatilhoRef = useRef<HTMLSpanElement>(null)
  const balaoRef = useRef<HTMLDivElement>(null)
  const timerRef = useRef<number | undefined>(undefined)

  const [aberto, setAberto] = useState(false)
  const [pos, setPos] = useState({ top: 0, left: 0, seta: 0, acima: false, medido: false })

  const fechar = useCallback(() => {
    window.clearTimeout(timerRef.current)
    setAberto(false)
    setPos((p) => ({ ...p, medido: false }))
  }, [])

  const abrir = useCallback(() => {
    window.clearTimeout(timerRef.current)
    timerRef.current = window.setTimeout(() => setAberto(true), delay)
  }, [delay])

  // Posiciona só depois que o balão existe no DOM, para usar a altura/largura reais.
  useLayoutEffect(() => {
    if (!aberto) return
    const gatilho = gatilhoRef.current?.getBoundingClientRect()
    const balao = balaoRef.current?.getBoundingClientRect()
    if (!gatilho || !balao) return

    const centro = gatilho.left + gatilho.width / 2
    // Abre para baixo (como no design); só sobe se não couber na janela.
    const acima = gatilho.bottom + ESPACO + balao.height > window.innerHeight - MARGEM
    const top = acima ? gatilho.top - balao.height - ESPACO : gatilho.bottom + ESPACO

    // Mantém o balão dentro da janela e desloca a seta na mesma medida, para
    // ela continuar apontando o gatilho mesmo com o balão "encostado" na borda.
    const metade = balao.width / 2
    const left = Math.min(Math.max(centro, MARGEM + metade), window.innerWidth - MARGEM - metade)

    setPos({ top, left, seta: centro - left, acima, medido: true })
  }, [aberto])

  // Rolagem e resize invalidam a posição calculada: fechar é mais honesto que
  // deixar o balão flutuando longe do elemento que o originou.
  useEffect(() => {
    if (!aberto) return
    const aoMover = () => fechar()
    const aoTeclar = (e: KeyboardEvent) => { if (e.key === 'Escape') fechar() }
    window.addEventListener('scroll', aoMover, true)
    window.addEventListener('resize', aoMover)
    window.addEventListener('keydown', aoTeclar)
    return () => {
      window.removeEventListener('scroll', aoMover, true)
      window.removeEventListener('resize', aoMover)
      window.removeEventListener('keydown', aoTeclar)
    }
  }, [aberto, fechar])

  useEffect(() => () => window.clearTimeout(timerRef.current), [])

  if (!label) return <>{children}</>

  return (
    <>
      <span
        ref={gatilhoRef}
        className={`inline-flex${className ? ` ${className}` : ''}`}
        onMouseEnter={abrir}
        onMouseLeave={fechar}
        onFocus={abrir}
        onBlur={fechar}
      >
        {children}
      </span>

      {aberto &&
        createPortal(
          <div
            ref={balaoRef}
            role="tooltip"
            style={{ top: pos.top, left: pos.left, opacity: pos.medido ? 1 : 0 }}
            className="pointer-events-none fixed z-[100] -translate-x-1/2 transition-opacity duration-100"
          >
            <div className="relative max-w-[260px] rounded-xl bg-[#18181B] px-3.5 py-2 text-[13px] font-medium leading-snug text-white shadow-lg">
              {label}
              <span
                aria-hidden="true"
                style={{ left: `calc(50% + ${pos.seta}px)` }}
                className={`absolute h-2.5 w-2.5 -translate-x-1/2 rotate-45 rounded-[2px] bg-[#18181B] ${
                  pos.acima ? '-bottom-1' : '-top-1'
                }`}
              />
            </div>
          </div>,
          document.body,
        )}
    </>
  )
}
