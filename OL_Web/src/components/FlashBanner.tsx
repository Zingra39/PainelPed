import type { Flash } from '../hooks/useFlash'

const ESTILO: Record<Flash['tipo'], string> = {
  sucesso: 'bg-green-50 text-green-700 border-green-200',
  erro:    'bg-red-50 text-red-700 border-red-200',
  aviso:   'bg-amber-50 text-amber-700 border-amber-200',
}

/** Exibe a mensagem de `useFlash`. `compacto` é a variante menor, usada dentro de cards. */
export default function FlashBanner({ flash, compacto = false }: { flash: Flash | null; compacto?: boolean }) {
  if (!flash) return null
  return (
    <div
      role={flash.tipo === 'erro' ? 'alert' : 'status'}
      className={`rounded-lg border ${ESTILO[flash.tipo]} ${
        compacto ? 'mb-3 px-3 py-2 text-xs' : 'mb-4 px-4 py-3 text-sm font-medium'
      }`}
    >
      {flash.texto}
    </div>
  )
}
