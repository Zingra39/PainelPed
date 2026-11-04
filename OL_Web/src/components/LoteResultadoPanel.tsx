import { useState } from 'react'
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, XCircle } from 'lucide-react'
import type { LoteResultado } from '../types'

/** Estado do painel: o resultado devolvido pela rota de lote, ou o erro da requisição. */
export type LoteEstado =
  | { titulo: string; resultado: LoteResultado; erro?: undefined }
  | { titulo: string; erro: string; resultado?: undefined }

interface Props {
  estado: LoteEstado | null
  /** Texto do cabeçalho quando nenhum pedido atendeu ao critério. */
  vazio?: string
  /** Texto do cabeçalho quando houve sucesso; padrão "X de Y processado(s) com sucesso." */
  descreverSucesso?: (r: LoteResultado) => string
  onClose?: () => void
  className?: string
}

const padraoSucesso = (r: LoteResultado) => `${r.sucesso} de ${r.total} processado(s) com sucesso.`

/**
 * Painel de resultado de uma ação em lote (F2 da auditoria): resumo colorido
 * pelo desfecho + lista das falhas, recolhível.
 *
 * Erro de requisição aparece como erro — antes as telas o convertiam num
 * resultado vazio, e o operador lia "Nenhum pedido encontrado" quando na
 * verdade a chamada tinha falhado.
 */
export default function LoteResultadoPanel({
  estado, vazio = 'Nenhum pedido encontrado para o critério selecionado.',
  descreverSucesso = padraoSucesso, onClose, className = 'mt-4',
}: Props) {
  const [aberto, setAberto] = useState(false)
  // Novo resultado recolhe a lista de falhas (ajuste de estado durante o
  // render, o padrão do React para "resetar quando a prop muda").
  const [estadoVisto, setEstadoVisto] = useState(estado)
  if (estado !== estadoVisto) {
    setEstadoVisto(estado)
    setAberto(false)
  }
  if (!estado) return null

  const { titulo, resultado } = estado
  const falhas = resultado?.detalhes.filter((d) => !d.sucesso) ?? []

  let tom = 'bg-green-50 border-green-200'
  let icone = <CheckCircle2 size={15} className="text-green-600" />
  let texto: string
  if (!resultado) {
    tom = 'bg-red-50 border-red-200'
    icone = <XCircle size={15} className="text-red-600" />
    texto = estado.erro
  } else {
    texto = resultado.total === 0 ? vazio : descreverSucesso(resultado)
    if (resultado.falha > 0) {
      tom = resultado.sucesso === 0 ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'
      icone = <AlertTriangle size={15} className="text-amber-600" />
    }
  }

  return (
    <div role="status" className={`${className} rounded-lg border p-4 text-sm ${tom}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {icone}
          <span className="font-medium text-slate-700">{titulo} — {texto}</span>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {falhas.length > 0 && (
            <button
              onClick={() => setAberto((v) => !v)}
              aria-expanded={aberto}
              className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
            >
              {falhas.length} falha(s)
              {aberto ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
          )}
          {onClose && (
            <button onClick={onClose} className="text-xs text-slate-400 hover:text-slate-600">
              Fechar
            </button>
          )}
        </div>
      </div>
      {aberto && falhas.length > 0 && (
        <div className="mt-3 space-y-1 max-h-48 overflow-y-auto rounded-lg bg-white border border-red-100 p-3">
          {falhas.map((d, i) => (
            <div key={`${d.numero_pedido_ol}-${i}`} className="flex gap-2 text-xs py-1 border-b border-slate-100 last:border-0">
              <span className="font-mono text-slate-600 shrink-0 w-48">{d.numero_pedido_ol}</span>
              <span className="text-red-600">{d.mensagem}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
