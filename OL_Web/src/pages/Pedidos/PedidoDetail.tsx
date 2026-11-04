import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { pedidosApi } from '../../api/pedidos'
import { arquivosApi } from '../../api/arquivos'
import StatusBadge from '../../components/StatusBadge'
import ConfirmDialog from '../../components/ConfirmDialog'
import { useAuth } from '../../contexts/AuthContext'
import {
  ArrowLeft, FileText, Printer, RotateCcw, XCircle,
  AlertTriangle, FileArchive, Clock, Download, Loader2,
  ChevronDown, ChevronUp, SendHorizontal, MessageSquare, Save,
  ClipboardCheck, CheckCircle2, UserCheck,
} from 'lucide-react'
import type { OcorrenciaItem, OcorrenciaPedido } from '../../types'
import { apiErr } from '../../lib/apiError'
import { rotuloStatus } from '../../lib/statusEnum'
import Tooltip from '../../components/Tooltip'
import AnalisadoBadge from '../../components/AnalisadoBadge'
import FlashBanner from '../../components/FlashBanner'
import { Button, IconButton } from '../../components/Button'
import { Th } from '../../components/Table'
import { useFlash } from '../../hooks/useFlash'
import { fmtData, fmtDataHora, fmtMoeda, fmtNumero, fmtPct } from '../../lib/format'
import {
  STATUS_EM_ANALISE, STATUS_PRONTO, podeGerarCancelamento, podeGerarEspelho, podeGerarRetorno,
} from '../../lib/statusConfig'

// "Em Analise": o operador marca o pedido da triagem como em análise para os
// demais saberem quem está cuidando dele. Só pedido Pronto/Verificar entra em
// análise (mesmo gate do backend, POST /pedidos/{id}/analise), e enquanto
// estiver nesse status ele não pode ser transmitido nem reprocessado.
const PODE_ANALISAR_STATUS = ['Pronto', 'Verificar']

// Campo de observação do layout Close-Up: 100 caracteres (posições 87 a 186
// do cabeçalho). O backend prefixa "<nome do usuário>: ", e esse prefixo
// consome parte do limite — por isso o textarea desconta o tamanho dele.
const LIMITE_OBSERVACAO = 100

/** Mesma normalização do backend (`_normalizar_observacao`): o layout é de
 *  largura fixa e um caractere acentuado ocupa 2 bytes em UTF-8, o que
 *  desalinharia as colunas. Aplicada aqui só para o prefixo do autor, para a
 *  tela mostrar exatamente o que será gravado no arquivo. */
function semAcento(texto: string) {
  return texto.normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
}


interface SectionProps {
  title: string
  icon?: React.ReactNode
  defaultOpen?: boolean
  children: React.ReactNode
}

function Section({ title, icon, defaultOpen = true, children }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden mb-4">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2 font-semibold text-slate-700 text-sm">
          {icon}
          {title}
        </div>
        {open ? <ChevronUp size={15} className="text-slate-400" /> : <ChevronDown size={15} className="text-slate-400" />}
      </button>
      {open && <div className="border-t border-slate-100">{children}</div>}
    </div>
  )
}

interface OcorrenciaRowProps {
  oc: OcorrenciaItem | OcorrenciaPedido
}
function OcorrenciaRow({ oc }: OcorrenciaRowProps) {
  return (
    <div className="px-5 py-4 flex items-start gap-4">
      {oc.severidade && <StatusBadge status={oc.severidade} />}
      <div className="min-w-0 flex-1">
        {oc.codigo && <span className="text-xs font-mono text-slate-400 mr-2">[{oc.codigo}]</span>}
        <span className="text-sm text-slate-700">{oc.descricao ?? '—'}</span>
        <p className="text-xs text-slate-400 mt-0.5">{fmtDataHora(oc.criado_em)}</p>
      </div>
      <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${
        oc.resolvido ? 'bg-green-100 text-green-600' : 'bg-amber-100 text-amber-600'
      }`}>
        {oc.resolvido ? 'Resolvido' : 'Aberta'}
      </span>
    </div>
  )
}

export default function PedidoDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { isOperacional, isAdmin, user } = useAuth()
  const flash = useFlash(5000)
  const [downloading, setDownloading] = useState<number | null>(null)
  const [gerandoPedido, setGerandoPedido] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [showConfirmTransmitir, setShowConfirmTransmitir] = useState(false)
  const [showConfirmEncerrarAnalise, setShowConfirmEncerrarAnalise] = useState(false)
  const [obsDraft, setObsDraft] = useState<string | null>(null)

  const { data: pedido, isLoading, isError, error } = useQuery({
    queryKey: ['pedido-detalhes', id],
    queryFn: () => pedidosApi.getDetalhes(Number(id)),
    enabled: !!id,
    // Serviços automáticos (retorno.py e afins) atualizam o status_operacional
    // direto no banco, sem passar por essa tela — sem polling o badge só
    // atualizaria com um refresh manual da página.
    refetchInterval: 15_000,
  })

  const showMsg = (ok: boolean, text: string) => flash.mostrar(ok ? 'sucesso' : 'erro', text)

  // As listas usam as chaves 'confeccao', 'rastreamento' e 'historico' — a
  // chave antiga ['pedidos'] não existia, e voltar à lista mostrava o status
  // antigo até o próximo polling (Q3 da auditoria).
  function invalidate() {
    qc.invalidateQueries({ queryKey: ['pedido-detalhes', id] })
    for (const lista of ['confeccao', 'rastreamento', 'historico']) {
      qc.invalidateQueries({ queryKey: [lista] })
    }
  }

  const retorno = useMutation({
    mutationFn: pedidosApi.gerarRetorno,
    onSuccess: () => { invalidate(); showMsg(true, 'Retorno executado com sucesso.') },
    onError: (e: unknown) => showMsg(false, apiErr(e, 'Erro ao gerar retorno.')),
  })
  const espelho = useMutation({
    mutationFn: pedidosApi.gerarEspelho,
    onSuccess: () => { invalidate(); showMsg(true, 'Espelho executado com sucesso.') },
    onError: (e: unknown) => showMsg(false, apiErr(e, 'Erro ao gerar espelho.')),
  })
  const reprocessar = useMutation({
    mutationFn: pedidosApi.reprocessar,
    onSuccess: () => { invalidate(); showMsg(true, 'Reprocessamento solicitado com sucesso.') },
    onError: (e: unknown) => showMsg(false, apiErr(e, 'Erro ao reprocessar.')),
  })
  const cancelar = useMutation({
    mutationFn: pedidosApi.cancelar,
    onSuccess: () => { invalidate(); showMsg(true, 'Cancelamento registrado com sucesso.') },
    onError: (e: unknown) => showMsg(false, apiErr(e, 'Erro ao cancelar.')),
  })
  const observacaoMut = useMutation({
    mutationFn: (texto: string) => pedidosApi.salvarObservacao(Number(id), texto),
    onSuccess: () => { invalidate(); setObsDraft(null); showMsg(true, 'Observação salva no pedido.') },
    onError: (e: unknown) => showMsg(false, apiErr(e, 'Erro ao salvar a observação.')),
  })
  const transmitir = useMutation({
    mutationFn: pedidosApi.transmitir,
    onSuccess: () => { invalidate(); showMsg(true, 'Pedido transmitido para a pasta de entrada da indústria.') },
    onError: (e: unknown) => showMsg(false, apiErr(e, 'Erro ao transmitir o pedido.')),
  })
  // Nos erros (ex.: 409 "já está em análise por fulano") também recarrega, para
  // a tela mostrar o estado real do pedido em vez do que estava na memória.
  const iniciarAnalise = useMutation({
    mutationFn: pedidosApi.iniciarAnalise,
    onSuccess: () => { invalidate(); showMsg(true, 'Pedido marcado como em análise.') },
    onError: (e: unknown) => { invalidate(); showMsg(false, apiErr(e, 'Erro ao marcar o pedido como em análise.')) },
  })
  const encerrarAnalise = useMutation({
    mutationFn: pedidosApi.encerrarAnalise,
    onSuccess: (res) => {
      invalidate()
      showMsg(true, res?.mensagem ?? 'Análise encerrada. O pedido foi reprocessado.')
    },
    onError: (e: unknown) => { invalidate(); showMsg(false, apiErr(e, 'Erro ao encerrar a análise.')) },
  })

  async function handleDownload(arqId: number, nome: string | null) {
    setDownloading(arqId)
    try { await arquivosApi.download(arqId, nome ?? `arquivo_${arqId}.txt`) }
    catch { showMsg(false, 'Arquivo não encontrado no servidor.') }
    finally { setDownloading(null) }
  }

  async function handleGerarPedido() {
    if (!pedido) return
    setGerandoPedido(true)
    try {
      const nome = pedido.nome_arquivo
        ? pedido.nome_arquivo.split(/[\\/]/).pop() ?? `PEDIDO_${pedido.numero_pedido_ol}.txt`
        : `PEDIDO_${pedido.numero_pedido_ol}.txt`
      const origem = await pedidosApi.gerarPedido(pedido.id, nome)
      if (origem === 'reconstruido') {
        flash.mostrar(
          'aviso',
          'Atenção: o arquivo original não foi encontrado no servidor — este download foi reconstruído a partir dos dados salvos no banco e pode estar incompleto ou divergente do original.',
        )
      }
    } catch {
      showMsg(false, 'Não foi possível gerar o arquivo de pedido.')
    } finally {
      setGerandoPedido(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (isError) {
    const msg = apiErr(error, 'Não foi possível carregar o pedido. Verifique a conexão com o servidor.')
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <p className="text-red-600 font-medium">{msg}</p>
        <button
          onClick={() => navigate(-1)}
          className="text-sm text-slate-500 hover:text-slate-700 underline"
        >
          Voltar para a lista
        </button>
      </div>
    )
  }

  if (!pedido) {
    return <div className="text-slate-500 py-10 text-center">Pedido não encontrado.</div>
  }

  const podeReprocessar = pedido.status_erp === 'Não Transmitido' &&
    ['Importado', 'Verificar', 'Falha no Reprocessamento'].includes(pedido.status_operacional ?? '')
  const podeRetorno = podeGerarRetorno(pedido)
  const podeEspelho = podeGerarEspelho(pedido)
  const podeCancelar = podeGerarCancelamento(pedido)
  // Em falha de geração, o botão vira "nova tentativa" (a geração dos pedidos
  // com falha é só manual — o serviço automático não reprocessa).
  const retornoFalhou = pedido.status_operacional === 'Falha no Retorno'
  const espelhoFalhou = pedido.status_operacional === 'Falha no Espelho'
  const cancelamentoFalhou = pedido.status_operacional === 'Falha no Cancelamento'
  // Mesmo gate do backend em POST /pedidos/{id}/transmitir: só quem ainda não
  // foi transmitido. Sem isso o botão apareceria só para receber 422.
  // Pedido em análise nunca é transmitido: primeiro se encerra a análise.
  const emAnalise = pedido.status_operacional === STATUS_EM_ANALISE
  const podeTransmitir = pedido.status_erp === 'Não Transmitido' && !emAnalise
  // Parâmetro BLOQUEAR_ENVIO_PEDIDO_VERIFICAR ligado: só "Pronto" é transmitido
  // (o backend também recusa com 422 — aqui só evitamos oferecer o que não passa).
  const envioBloqueado = !!pedido.envio_somente_pronto && pedido.status_operacional !== STATUS_PRONTO
  const podeAnalisar = pedido.status_erp === 'Não Transmitido' &&
    PODE_ANALISAR_STATUS.includes(pedido.status_operacional ?? '')
  // Encerra quem iniciou a análise ou um Administrador (para destravar pedido
  // deixado em análise por quem saiu sem encerrar) — mesma regra do backend.
  const souAutorDaAnalise = !!user && pedido.id_usuario_analise === user.id
  const podeEncerrarAnalise = emAnalise && (souAutorDaAnalise || isAdmin)

  // Observação só na triagem: depois de transmitido o arquivo já saiu, e
  // editar aqui daria a falsa impressão de ter mudado o que foi enviado.
  const podeObservar = pedido.status_erp === 'Não Transmitido'
  const obsSalva = pedido.observacao ?? ''
  // Sem nome no perfil o backend grava só o texto, sem prefixo — o campo
  // acompanha, para o limite dos dois lados bater exatamente.
  const autorNome = semAcento(user?.nome ?? '').trim()
  const autorPrefixo = autorNome ? `${autorNome}:` : ''
  const meuPrefixo = autorNome ? `${autorPrefixo} ` : ''
  const limiteObs = Math.max(0, LIMITE_OBSERVACAO - meuPrefixo.length)
  // Se a observação atual é deste usuário, ela volta para o campo pronta para
  // edição; se foi outra pessoa, o campo começa vazio e o valor atual fica
  // visível acima, para não parecer que estou reescrevendo em nome dela.
  const obsTexto = obsDraft ?? (obsSalva.startsWith(meuPrefixo) ? obsSalva.slice(meuPrefixo.length) : '')

  const acaoEmAndamento =
    retorno.isPending ? 'Gerando Retorno' :
    espelho.isPending ? 'Gerando Espelho' :
    reprocessar.isPending ? 'Reprocessando' :
    cancelar.isPending ? 'Cancelando' :
    transmitir.isPending ? 'Transmitindo' :
    // Encerrar a análise reprocessa o pedido, então o status em andamento é o mesmo.
    encerrarAnalise.isPending ? 'Reprocessando' : null
  const anyPending = !!acaoEmAndamento || iniciarAnalise.isPending

  const errosAbertos = pedido.ocorrencias.filter((o) => !o.resolvido)
  const todosErros: (OcorrenciaPedido | OcorrenciaItem)[] = [
    ...pedido.ocorrencias,
    ...pedido.itens.flatMap((it) => it.ocorrencias ?? []),
  ]

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div className="flex items-start gap-3">
          <IconButton label="Voltar" appearance="outline" onClick={() => navigate(-1)} className="mt-0.5">
            <ArrowLeft size={15} />
          </IconButton>
          <div>
            <h1 className="text-lg font-semibold text-slate-800 font-mono">{pedido.numero_pedido_ol}</h1>
            <p className="text-sm text-slate-500 mt-0.5">
              {pedido.industria_nome} · {fmtData(pedido.data_pedido)}
            </p>
          </div>
        </div>

        {isOperacional && (
          <div className="flex items-center gap-2 flex-wrap justify-end">
            <Tooltip label="Este arquivo é gerado com base nos dados salvos da importação">
              <Button onClick={handleGerarPedido} loading={gerandoPedido} icon={<Download size={14} />}>
                Baixar Pedido
              </Button>
            </Tooltip>
            {podeAnalisar && (
              <Tooltip label="Avisa aos demais usuários que você está analisando este pedido e impede que ele seja transmitido">
                <button
                  onClick={() => iniciarAnalise.mutate(pedido.id)}
                  disabled={anyPending}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-violet-300 bg-white hover:bg-violet-50 hover:border-violet-400 text-sm text-violet-700 transition-colors disabled:opacity-50"
                >
                  {iniciarAnalise.isPending ? <Loader2 size={14} className="animate-spin" /> : <ClipboardCheck size={14} />}
                  Analisar
                </button>
              </Tooltip>
            )}
            {podeEncerrarAnalise && (
              <Tooltip label="Encerra a análise e reprocessa o pedido, que volta como Pronto ou Verificar">
                <button
                  onClick={() => setShowConfirmEncerrarAnalise(true)}
                  disabled={anyPending}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-violet-300 bg-violet-600 hover:bg-violet-700 text-sm text-white transition-colors disabled:opacity-50"
                >
                  {encerrarAnalise.isPending ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                  Encerrar análise
                </button>
              </Tooltip>
            )}
            {podeTransmitir && (
              <Tooltip
                label={
                  envioBloqueado
                    ? 'Envio bloqueado pela parametrização — só pedidos "Pronto" podem ser transmitidos. Resolva as ocorrências e reprocesse o pedido.'
                    : 'Envia arquivo para transmissão'
                }
              >
                <button
                  onClick={() => {
                    // Pedido com ocorrência aberta passa por confirmação, igual
                    // ao fluxo da Confecção; sem ocorrência transmite direto.
                    if (errosAbertos.length > 0) setShowConfirmTransmitir(true)
                    else transmitir.mutate(pedido.id)
                  }}
                  disabled={anyPending || envioBloqueado}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border border-green-300 bg-white hover:bg-green-50 hover:border-green-400 text-sm text-green-700 transition-colors disabled:opacity-50 ${
                    envioBloqueado ? 'pointer-events-none' : ''
                  }`}
                >
                  {transmitir.isPending ? <Loader2 size={14} className="animate-spin" /> : <SendHorizontal size={14} />}
                  Transmitir
                </button>
              </Tooltip>
            )}
            {podeRetorno && (
              <button
                onClick={() => retorno.mutate(pedido.id)}
                disabled={anyPending}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-300 bg-white hover:bg-blue-50 hover:border-blue-300 hover:text-blue-600 text-sm text-slate-600 transition-colors disabled:opacity-50"
              >
                {retorno.isPending ? <Loader2 size={14} className="animate-spin" /> : <FileText size={14} />} {retornoFalhou ? 'Tentar Retorno Novamente' : pedido.retorno_manual_liberado ? 'Gerar Retorno (atrasado há +1h)' : 'Gerar Retorno'}
              </button>
            )}
            {podeEspelho && (
              <button
                onClick={() => espelho.mutate(pedido.id)}
                disabled={anyPending}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-300 bg-white hover:bg-teal-50 hover:border-teal-300 hover:text-teal-600 text-sm text-slate-600 transition-colors disabled:opacity-50"
              >
                {espelho.isPending ? <Loader2 size={14} className="animate-spin" /> : <Printer size={14} />} {espelhoFalhou ? 'Tentar Espelho Novamente' : 'Gerar Espelho'}
              </button>
            )}
            {podeReprocessar && (
              <button
                onClick={() => reprocessar.mutate(pedido.id)}
                disabled={anyPending}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-300 bg-white hover:bg-amber-50 hover:border-amber-300 hover:text-amber-600 text-sm text-slate-600 transition-colors disabled:opacity-50"
              >
                {reprocessar.isPending ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />} Reprocessar
              </button>
            )}
            {podeCancelar && (
              <button
                onClick={() => setShowConfirm(true)}
                disabled={anyPending}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-red-200 bg-red-50 hover:bg-red-100 text-red-600 text-sm transition-colors disabled:opacity-50"
              >
                {cancelar.isPending ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />} {cancelamentoFalhou ? 'Tentar Cancelamento Novamente' : 'Cancelar'}
              </button>
            )}
          </div>
        )}
      </div>

      <FlashBanner flash={flash.flash} />

      {/* Aviso de análise — visível a todos os perfis, é o que diz aos demais
          usuários que alguém está cuidando deste pedido. */}
      {emAnalise && (
        <div className="mb-4 flex items-start gap-3 px-4 py-3 rounded-lg border border-violet-200 bg-violet-50 text-sm text-violet-800">
          <UserCheck size={16} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">
              {souAutorDaAnalise
                ? 'Você está analisando este pedido'
                : `Em análise por ${pedido.em_analise_por ?? 'outro usuário'}`}
              {pedido.em_analise_desde ? ` desde ${fmtDataHora(pedido.em_analise_desde)}` : ''}.
            </p>
            <p className="text-xs text-violet-700 mt-0.5">
              Enquanto estiver em análise o pedido não pode ser transmitido nem reprocessado.
              {podeEncerrarAnalise
                ? ' Ao encerrar a análise o pedido é reprocessado e volta como Pronto ou Verificar.'
                : ' Só quem iniciou a análise (ou um Administrador) pode encerrá-la.'}
            </p>
          </div>
        </div>
      )}

      {/* 1. Informações do pedido */}
      <Section title="Informações do pedido">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-slate-100">
          {[
            { label: 'Número OL',       value: pedido.numero_pedido_ol ?? '—' },
            { label: 'Arquivo',         value: pedido.nome_arquivo?.split(/[\\/]/).pop() ?? '—' },
            { label: 'Código Interno ERP',  value: pedido.codigo_interno_erp ?? '—' },
            { label: 'Data de entrada', value: fmtDataHora(pedido.data_pedido) },
            { label: 'Indústria',       value: pedido.industria_nome ?? '—' },
            { label: 'Valor Total',     value: fmtMoeda(pedido.valor_total) },
            { label: 'Ocorr. abertas',  value: String(errosAbertos.length) },
            { label: 'Atualizado em',   value: fmtDataHora(pedido.atualizado_em) },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white px-4 py-3">
              <p className="text-xs text-slate-400 mb-1">{label}</p>
              <p className="text-sm font-medium text-slate-800 font-mono">{value}</p>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-px bg-slate-100">
          <div className="bg-white px-4 py-3">
            <p className="text-xs text-slate-400 mb-1.5">Status Operacional</p>
            <div className="flex items-center gap-1.5">
              {acaoEmAndamento
                ? <StatusBadge status={acaoEmAndamento} size="md" />
                : pedido.status_operacional
                  ? <StatusBadge status={pedido.status_operacional} size="md" />
                  : <span className="text-slate-300 text-sm">—</span>}
              {anyPending && <Loader2 size={13} className="animate-spin text-slate-400" />}
              <AnalisadoBadge por={pedido.analisado_por} em={pedido.analisado_em} size="md" />
            </div>
          </div>
          <div className="bg-white px-4 py-3">
            <p className="text-xs text-slate-400 mb-1.5">Status ERP</p>
            {pedido.status_erp
              ? <StatusBadge status={rotuloStatus(pedido.status_erp)} size="md" />
              : <span className="text-slate-300 text-sm">—</span>}
          </div>
        </div>
      </Section>

      {/* 2. Informações do cliente */}
      <Section title="Informações do cliente">
        <div className="grid grid-cols-2 md:grid-cols-2 gap-px bg-slate-100">
          {[
            { label: 'CNPJ',      value: pedido.cnpj_cliente ?? '—' },
            { label: 'Indústria', value: pedido.industria_nome ?? '—' },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white px-4 py-3">
              <p className="text-xs text-slate-400 mb-1">{label}</p>
              <p className="text-sm font-medium text-slate-800 font-mono">{value}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* 3. Observação da triagem — vai para o arquivo do pedido */}
      <Section title="Observação" icon={<MessageSquare size={14} className="text-slate-400" />}>
        <div className="px-5 py-4">
          {obsSalva && !obsSalva.startsWith(meuPrefixo) && (
            <div className="mb-3 rounded-lg bg-slate-50 border border-slate-200 px-3 py-2">
              <p className="text-xs text-slate-400 mb-0.5">Observação atual</p>
              <p className="text-sm text-slate-700 break-words">{obsSalva}</p>
            </div>
          )}

          {podeObservar && isOperacional ? (
            <>
              <div className="flex items-start gap-2">
                {autorPrefixo && (
                  <span className="mt-2 text-sm font-semibold text-slate-600 shrink-0">{autorPrefixo}</span>
                )}
                <textarea
                  value={obsTexto}
                  onChange={(e) => setObsDraft(e.target.value.slice(0, limiteObs))}
                  maxLength={limiteObs}
                  rows={2}
                  placeholder="Ex.: PRAZO 30/60"
                  className="flex-1 px-3 py-2 rounded-lg border border-slate-300 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="mt-2 flex items-center justify-between gap-3 flex-wrap">
                <p className="text-xs text-slate-400">
                  Entra no arquivo do pedido, no campo de observação do cabeçalho, no momento da transmissão.
                </p>
                <div className="flex items-center gap-3">
                  <span className={`text-xs tabular-nums ${obsTexto.length >= limiteObs ? 'text-amber-600' : 'text-slate-400'}`}>
                    {obsTexto.length}/{limiteObs}
                  </span>
                  <button
                    onClick={() => observacaoMut.mutate(obsTexto.trim())}
                    disabled={observacaoMut.isPending || anyPending}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-sm text-slate-600 transition-colors disabled:opacity-50"
                  >
                    {observacaoMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                    Salvar
                  </button>
                </div>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm text-slate-700 break-words">{obsSalva || '—'}</p>
              <p className="mt-2 text-xs text-slate-400">
                {podeObservar
                  ? 'Somente leitura: seu perfil não permite editar a observação.'
                  : 'Somente leitura: o pedido já saiu da triagem, e o arquivo já foi transmitido com a observação acima.'}
              </p>
            </>
          )}
        </div>
      </Section>

      {/* 3. Itens do pedido */}
      <Section title={`Itens do pedido (${pedido.itens.length})`}>
        {pedido.itens.length === 0 ? (
          <p className="px-5 py-8 text-center text-slate-400 text-sm">Nenhum item</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100">
                  <Th>EAN</Th>
                  <Th align="center">Cód. ERP</Th>
                  <Th align="center">Qtd. Solicitada</Th>
                  <Th align="center">Qtd. Atendida</Th>
                  <Th align="center">Preço</Th>
                  <Th align="center">Desconto</Th>
                  <Th align="center">Status</Th>
                  <Th align="center">Cond.</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {pedido.itens.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-xs text-slate-600">{item.ean ?? '—'}</td>
                    <td className="px-4 py-3 text-center font-mono text-xs text-slate-500">{item.codigo_produto_erp ?? '—'}</td>
                    <td className="px-4 py-3 text-center text-slate-700">{fmtNumero(item.quantidade_solicitada)}</td>
                    <td className="px-4 py-3 text-center font-semibold text-slate-800">{fmtNumero(item.quantidade_atendida)}</td>
                    <td className="px-4 py-3 text-center text-slate-600">{fmtMoeda(item.preco)}</td>
                    <td className="px-4 py-3 text-center text-slate-500">{fmtPct(item.desconto)}</td>
                    <td className="px-4 py-3">
                      {item.status ? <StatusBadge status={item.status} /> : <span className="text-slate-300">—</span>}
                    </td>
                    <td className="px-4 py-3 text-center text-slate-500">{item.id_cond ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {/* 5. Erros e ocorrências */}
      {todosErros.length > 0 && (
        <Section
          title={`Erros e ocorrências (${todosErros.length})`}
          icon={<AlertTriangle size={14} className="text-amber-500" />}
        >
          <div className="divide-y divide-slate-100">
            {todosErros.map((oc) => (
              <OcorrenciaRow key={oc.id} oc={oc} />
            ))}
          </div>
        </Section>
      )}

      {/* Arquivos */}
      <Section
        title={`Arquivos (${pedido.arquivos.length})`}
        icon={<FileArchive size={14} className="text-slate-400" />}
        defaultOpen={false}
      >
        {pedido.arquivos.length === 0 ? (
          <p className="px-5 py-8 text-center text-slate-400 text-sm">Nenhum arquivo</p>
        ) : (
          <div className="divide-y divide-slate-100">
            {pedido.arquivos.map((a) => (
              <div key={a.id} className="px-5 py-3 flex items-center gap-3">
                <FileArchive size={14} className="text-slate-300 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-slate-700 truncate">{a.nome ?? '—'}</p>
                  <p className="text-xs text-slate-400">{a.tipo ?? ''} · {fmtData(a.criado_em)}</p>
                </div>
                {a.situacao && <StatusBadge status={a.situacao} />}
                <button
                  onClick={() => handleDownload(a.id, a.nome)}
                  disabled={downloading === a.id}
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {downloading === a.id
                    ? <Loader2 size={11} className="animate-spin" />
                    : <Download size={11} />}
                  Baixar
                </button>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Histórico */}
      <Section
        title={`Histórico (${pedido.historico.length})`}
        icon={<Clock size={14} className="text-slate-400" />}
        defaultOpen={false}
      >
        {pedido.historico.length === 0 ? (
          <p className="px-5 py-8 text-center text-slate-400 text-sm">Nenhum histórico</p>
        ) : (
          <div className="divide-y divide-slate-100">
            {pedido.historico.map((h) => (
              <div key={h.id} className="px-5 py-4 flex items-start gap-4">
                <div className="w-2 h-2 mt-1.5 rounded-full bg-blue-400 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-700">{h.acao ?? '—'}</p>
                  {h.detalhe && <p className="text-xs text-slate-500 mt-0.5">{h.detalhe}</p>}
                  {h.usuario_nome && <p className="text-xs text-slate-400 mt-0.5">por {h.usuario_nome}</p>}
                </div>
                <span className="text-xs text-slate-400 shrink-0">{fmtDataHora(h.criado_em)}</span>
              </div>
            ))}
          </div>
        )}
      </Section>

      <ConfirmDialog
        open={showConfirmTransmitir}
        title="Transmitir pedido com ocorrências em aberto?"
        description={`Este pedido possui ${errosAbertos.length} ocorrência(s) em aberto. Transmitir mesmo assim envia o arquivo para a pasta de entrada da indústria.`}
        confirmLabel="Transmitir"
        onConfirm={() => { transmitir.mutate(pedido.id); setShowConfirmTransmitir(false) }}
        onCancel={() => setShowConfirmTransmitir(false)}
      />

      <ConfirmDialog
        open={showConfirmEncerrarAnalise}
        title="Encerrar análise?"
        description="O pedido será reprocessado para revalidar o resultado da análise e voltará como Pronto (sem pendências) ou Verificar (com ocorrências). Depois disso ele poderá ser transmitido."
        confirmLabel="Encerrar análise"
        variant="primary"
        onConfirm={() => { encerrarAnalise.mutate(pedido.id); setShowConfirmEncerrarAnalise(false) }}
        onCancel={() => setShowConfirmEncerrarAnalise(false)}
      />

      <ConfirmDialog
        open={showConfirm}
        title="Cancelar pedido"
        description={`Confirmar o cancelamento do pedido ${pedido.numero_pedido_ol}?`}
        confirmLabel="Cancelar pedido"
        onConfirm={() => { cancelar.mutate(pedido.id); setShowConfirm(false) }}
        onCancel={() => setShowConfirm(false)}
      />
    </div>
  )
}
