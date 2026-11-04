import { useId } from 'react'
import Modal from './Modal'

interface ConfirmDialogProps {
  open: boolean
  title: string
  description?: string
  confirmLabel?: string
  /** 'danger' (padrão) pra ações destrutivas/irreversíveis (excluir, etc.);
   *  'primary' pra ações que só mudam um comportamento (ex.: ligar um
   *  parâmetro) — usa a cor de destaque da marca em vez de vermelho, que
   *  ficaria lendo como "isso vai apagar algo". */
  variant?: 'danger' | 'primary'
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirmar',
  variant = 'danger',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const tituloId = useId()
  const descricaoId = useId()

  return (
    <Modal aberto={open} onFechar={onCancel} tituloId={tituloId} descricaoId={description ? descricaoId : undefined} className="max-w-sm p-6 rounded-xl shadow-lg">
      <h2 id={tituloId} className="text-base font-semibold text-slate-800 mb-1">{title}</h2>
      {description ? (
        <p id={descricaoId} className="text-sm text-slate-500 mb-5">{description}</p>
      ) : (
        <div className="mb-5" />
      )}
      <div className="flex gap-3 justify-end">
        {/* Foco inicial no "Cancelar" (primeiro botão): Enter por engano não
            dispara a ação confirmada. */}
        <button
          onClick={onCancel}
          className="px-4 py-2 text-sm text-slate-600 border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors"
        >
          Cancelar
        </button>
        <button
          onClick={onConfirm}
          className={`px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors ${
            variant === 'primary' ? 'bg-brand hover:bg-brand-dark' : 'bg-red-500 hover:bg-red-600'
          }`}
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  )
}
