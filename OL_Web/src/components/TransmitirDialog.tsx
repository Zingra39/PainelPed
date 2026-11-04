import { useId } from 'react'
import { AlertTriangle, CheckCircle2 } from 'lucide-react'
import Modal from './Modal'

interface TransmitirDialogProps {
  open: boolean
  /** Parâmetro BLOQUEAR_ENVIO_PEDIDO_VERIFICAR ligado: o lote só leva pedidos "Pronto". */
  somentePronto?: boolean
  onConfirm: (apenasSemOcorrencia: boolean) => void
  onCancel: () => void
}

export default function TransmitirDialog({ open, somentePronto = false, onConfirm, onCancel }: TransmitirDialogProps) {
  const tituloId = useId()
  const descricaoId = useId()

  return (
    <Modal aberto={open} onFechar={onCancel} tituloId={tituloId} descricaoId={descricaoId} className="max-w-md p-6 rounded-xl shadow-lg">
        <h2 id={tituloId} className="text-base font-semibold text-slate-800 mb-1">Transmitir Arquivos</h2>
        <p id={descricaoId} className="text-sm text-slate-500 mb-5">
          Escolha quais pedidos com Status ERP <strong>"Não Transmitido"</strong> deseja copiar
          para a pasta de entrada da indústria.
        </p>

        {somentePronto ? (
          <div className="flex flex-col gap-3 mb-5">
            <button
              onClick={() => onConfirm(false)}
              className="flex items-start gap-3 p-4 rounded-xl border-2 border-green-200 bg-green-50 hover:bg-green-100 hover:border-green-400 text-left transition-colors group"
            >
              <CheckCircle2 size={20} className="text-green-600 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-slate-800 group-hover:text-green-800">
                  Transmitir pedidos Prontos
                </p>
                <p className="text-xs text-slate-500 mt-0.5">
                  Envia os pedidos com status "Pronto". Pedidos em "Verificar" ficam de fora: o envio
                  está bloqueado pela parametrização até a ocorrência ser resolvida.
                </p>
              </div>
            </button>
          </div>
        ) : (
        <div className="flex flex-col gap-3 mb-5">
          <button
            onClick={() => onConfirm(true)}
            className="flex items-start gap-3 p-4 rounded-xl border-2 border-green-200 bg-green-50 hover:bg-green-100 hover:border-green-400 text-left transition-colors group"
          >
            <CheckCircle2 size={20} className="text-green-600 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-slate-800 group-hover:text-green-800">
                Apenas sem ocorrências
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                Envia somente pedidos que não possuem ocorrências abertas.
              </p>
            </div>
          </button>

          <button
            onClick={() => onConfirm(false)}
            className="flex items-start gap-3 p-4 rounded-xl border-2 border-amber-200 bg-amber-50 hover:bg-amber-100 hover:border-amber-400 text-left transition-colors group"
          >
            <AlertTriangle size={20} className="text-amber-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-slate-800 group-hover:text-amber-800">
                Transmitir todos
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                Envia todos os pedidos "Não Transmitidos", incluindo os que possuem ocorrências abertas.
              </p>
            </div>
          </button>
        </div>
        )}

        <div className="flex justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm text-slate-600 border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors"
          >
            Cancelar
          </button>
        </div>
    </Modal>
  )
}
