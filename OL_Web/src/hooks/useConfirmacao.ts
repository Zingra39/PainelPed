import { useState } from 'react'

/**
 * Fluxo prévia -> confirmação -> execução das ações em lote (F7 da auditoria).
 *
 * Guarda o que o usuário está prestes a confirmar (`valor`) e, opcionalmente,
 * busca antes a prévia (quantos pedidos serão afetados) com `abrirComPrevia`.
 * Uso com o ConfirmDialog:
 *
 *   const conf = useConfirmacao<{ total: number }>()
 *   <ConfirmDialog open={conf.aberto} onCancel={conf.fechar} onConfirm={conf.confirmar(executar)} … />
 */
export function useConfirmacao<T>() {
  const [valor, setValor] = useState<T | null>(null)
  const [carregando, setCarregando] = useState(false)

  const fechar = () => setValor(null)

  return {
    valor,
    aberto: valor !== null,
    /** Verdadeiro enquanto a prévia está sendo buscada. */
    carregando,
    abrir: (v: T) => setValor(v),
    fechar,
    /** Busca a prévia e abre a confirmação com o resultado. Erro vai para `onErro`, sem abrir. */
    abrirComPrevia: async (carregar: () => Promise<T>, onErro: (e: unknown) => void) => {
      setCarregando(true)
      try {
        setValor(await carregar())
      } catch (e) {
        onErro(e)
      } finally {
        setCarregando(false)
      }
    },
    /** Handler do botão "confirmar": fecha o diálogo e executa com o valor confirmado. */
    confirmar: (executar: (v: T) => void) => () => {
      const v = valor
      setValor(null)
      if (v !== null) executar(v)
    },
  }
}
