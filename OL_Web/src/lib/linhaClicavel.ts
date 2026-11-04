import type { KeyboardEvent } from 'react'

/** Classes de foco visível para linha de tabela que abre um detalhe. */
export const LINHA_CLICAVEL_CLASS =
  'cursor-pointer focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand'

/**
 * Props para uma `<tr>` que abre um detalhe ao ser clicada (Q5 da auditoria):
 * a linha entra na ordem de Tab e abre com Enter ou Espaço, não só com o mouse.
 * (Sem `aria-label` na linha de propósito: ele substituiria a leitura das
 * células pelo leitor de tela.)
 *
 * Teclas pressionadas nos controles de dentro da linha (checkbox, botões de
 * ação) são ignoradas aqui — só a própria linha focada abre o detalhe.
 */
export function linhaClicavel(abrir: () => void) {
  return {
    tabIndex: 0,
    onClick: abrir,
    onKeyDown: (e: KeyboardEvent<HTMLElement>) => {
      if (e.target !== e.currentTarget) return
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        abrir()
      }
    },
  }
}
