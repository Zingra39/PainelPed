interface SwitchProps {
  checked: boolean
  onChange: () => void
  disabled?: boolean
  label: string
}

/**
 * Toggle liga/desliga — primeiro do app (tela de Parametrização). Estado
 * "ligado" em verde (mesma cor semântica já usada nas badges de status
 * online/ok em Servicos.tsx), nunca a cor de destaque da marca — o laranja
 * fica reservado pra ação/destaque, não pra estado.
 */
export default function Switch({ checked, onChange, disabled, label }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={onChange}
      className={`relative w-11 h-6 rounded-full transition-colors shrink-0 disabled:opacity-50 disabled:cursor-not-allowed ${
        checked ? 'bg-green-500' : 'bg-slate-300'
      }`}
    >
      <span
        className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
          checked ? 'translate-x-[19px]' : ''
        }`}
      />
    </button>
  )
}
