import { memo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { pedidosApi, type ConfeccaoFilter } from '../../api/pedidos'
import { apiErr, apiErrBlob } from '../../lib/apiError'
import type { LoteResultado, PedidoListItem } from '../../types'
import StatusBadge from '../../components/StatusBadge'
import Pagination from '../../components/Pagination'
import ConfirmDialog from '../../components/ConfirmDialog'
import TransmitirDialog from '../../components/TransmitirDialog'
import { useAuth } from '../../contexts/AuthContext'
import {
  RefreshCw, ChevronRight,
  RotateCcw, Loader2, CalendarRange, AlertTriangle,
  SendHorizontal, Download, UserCheck, Lock,
} from 'lucide-react'
import Tooltip from '../../components/Tooltip'
import AnalisadoBadge from '../../components/AnalisadoBadge'
import FilterBar, { FiltroSelect, FilterToggleButton } from '../../components/FilterBar'
import FlashBanner from '../../components/FlashBanner'
import LoteResultadoPanel, { type LoteEstado } from '../../components/LoteResultadoPanel'
import BulkBar from '../../components/BulkBar'
import { Button, IconButton } from '../../components/Button'
import { TableHead, TableFeedback, type Coluna } from '../../components/Table'
import { exibirStatus } from '../../lib/statusEnum'
import { fmtData, fmtDataHora } from '../../lib/format'
import { executarEmLote, resumoLote } from '../../lib/lote'
import { opcoesLista } from '../../lib/queryOpcoes'
import { STATUS_EM_ANALISE, STATUS_PRONTO } from '../../lib/statusConfig'
import { useFlash } from '../../hooks/useFlash'
import { useSelecao } from '../../hooks/useSelecao'
import { useConfirmacao } from '../../hooks/useConfirmacao'
import { useListFilters } from '../../hooks/useListFilters'
import { useEventCallback } from '../../hooks/useEventCallback'
import { LINHA_CLICAVEL_CLASS, linhaClicavel } from '../../lib/linhaClicavel'

// Valores reais de status_operacional retornados pela API para pedidos "Não
// Transmitido" (ver TipoStatusOper no backend) — o dropdown usava rótulos
// antigos que não existem mais, então o filtro por status nunca funcionava.
const STATUS_CONFECCAO = [
  'Importado', 'Verificar', 'Em Analise', 'Reprocessando', 'Falha no Reprocessamento', 'Pronto', 'Transmitindo', 'Falha',
]

// "Falha no Reprocessamento": o reprocessamento anterior foi desfeito (rollback) — tentar de novo é o caminho.
const REPROCESSAR_ROW_STATUS = ['Importado', 'Verificar', 'Falha', 'Falha no Reprocessamento']
const PODE_TRANSMITIR_ROW_STATUS = ['Pronto', 'Verificar']
// Parâmetro BLOQUEAR_ENVIO_PEDIDO_VERIFICAR ligado (a API devolve `envio_somente_pronto`):
// só "Pronto" é transmitido; o backend também recusa o resto, aqui só evitamos oferecer o que dá 422.
const MSG_ENVIO_BLOQUEADO = 'Envio bloqueado pela parametrização — só pedidos "Pronto" podem ser transmitidos.'

type AcaoLinha = 'reprocessar' | 'transmitir'
interface Periodo { data_inicio?: string; data_fim?: string }
interface PedidoReprocessar { apenasErro: boolean; todos: boolean; periodo: Periodo; total: number }

export default function Confeccao() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { isOperacional } = useAuth()
  const flash = useFlash()
  const lf = useListFilters<ConfeccaoFilter>({ page: 1, size: 20 })
  const { filters } = lf

  // Ações em lote disparadas pela seleção (uma requisição por pedido).
  const [emLote, setEmLote] = useState<{ acao: AcaoLinha; ids: Set<number> } | null>(null)

  const [showReprocessar, setShowReprocessar] = useState(false)
  const [reprocessarPending, setReprocessarPending] = useState(false)
  const [reprocessarResult, setReprocessarResult] = useState<LoteEstado | null>(null)

  const [transmitirDialogOpen, setTransmitirDialogOpen] = useState(false)
  const [transmitirPending, setTransmitirPending] = useState(false)
  const [transmitirResult, setTransmitirResult] = useState<LoteEstado | null>(null)

  // Confirmação com contagem prévia — ações em lote só disparam depois que o
  // usuário vê quantos pedidos serão afetados e confirma.
  const confReprocessar = useConfirmacao<PedidoReprocessar>()
  const confBulkReprocessar = useConfirmacao<{ ids: number[] }>()
  const confTransmitirLote = useConfirmacao<{ apenasSemOcorrencia: boolean; total: number }>()
  const confTransmitirSel = useConfirmacao<{ ids: number[]; algumComOcorrencia: boolean; ignorados: number }>()

  const { data, isLoading, isFetching, isError, error, refetch, isPlaceholderData } = useQuery({
    queryKey: ['confeccao', filters],
    queryFn: () => pedidosApi.confeccaoList(filters),
    // Serviços automáticos (reprocessamento, transmissão etc.) atualizam o
    // status_operacional direto no banco, sem passar por essa tela — sem
    // polling o badge só atualizaria com um refresh manual da página.
    ...opcoesLista(15_000),
  })
  const items = data?.items ?? []
  const invalidar = () => qc.invalidateQueries({ queryKey: ['confeccao'] })

  const envioSomentePronto = data?.envio_somente_pronto ?? false
  const envioBloqueado = (status: string | null | undefined) => envioSomentePronto && status !== STATUS_PRONTO

  // Só pedidos fora de análise são selecionáveis em lote.
  const sel = useSelecao(
    items.filter((p) => p.status_operacional !== STATUS_EM_ANALISE).map((p) => p.id),
    filters,
  )
  const numeroDoPedido = (id: number) => items.find((p) => p.id === id)?.numero_pedido_ol ?? String(id)

  const exportar = useMutation({
    mutationFn: () => pedidosApi.exportConfeccao(filters),
    onError: async (e: unknown) => flash.erro(await apiErrBlob(e, 'Não foi possível exportar a planilha.')),
  })

  async function executarSelecionados(acao: AcaoLinha, ids: number[]) {
    setEmLote({ acao, ids: new Set(ids) })
    const fn = acao === 'reprocessar' ? pedidosApi.reprocessar : pedidosApi.transmitir
    const res = await executarEmLote(ids, fn, numeroDoPedido)
    sel.limpar()
    invalidar()
    setEmLote(null)
    const r = resumoLote(res, acao === 'reprocessar' ? 'Reprocessamento' : 'Transmissão')
    flash.mostrar(r.ok ? 'sucesso' : 'erro', r.texto)
  }

  // Transmissão de um único pedido (ação de linha) segue direto quando não há
  // ocorrência aberta — não é uma ação em lote. Só confirma com contagem
  // quando há mais de um pedido envolvido (seleção múltipla) ou quando algum
  // deles tem ocorrência aberta.
  function solicitarTransmissao(todosIds: number[]) {
    // Com o envio restrito a "Pronto", quem não está pronto fica de fora.
    const ids = todosIds.filter((id) => {
      const item = items.find((it) => it.id === id)
      return !(item && envioBloqueado(item.status_operacional))
    })
    const ignorados = todosIds.length - ids.length
    if (ids.length === 0) {
      flash.erro(MSG_ENVIO_BLOQUEADO)
      return
    }
    const algumComOcorrencia = ids.some(
      (id) => (items.find((it) => it.id === id)?.total_ocorrencias_abertas ?? 0) > 0
    )
    if (ids.length > 1 || algumComOcorrencia || ignorados > 0) {
      confTransmitirSel.abrir({ ids, algumComOcorrencia, ignorados })
    } else {
      executarTransmissaoDireta(ids)
    }
  }

  function executarTransmissaoDireta(ids: number[]) {
    if (ids.length === 1) transmitirItem.mutate(ids[0])
    else executarSelecionados('transmitir', ids)
  }

  // Busca quantos pedidos o critério afeta (rota de prévia, só leitura) antes
  // de abrir a confirmação — a execução real só acontece se confirmado. O
  // período vai junto na confirmação, para executar exatamente o que foi contado.
  function solicitarReprocessar(apenasErro: boolean, todos: boolean, periodoDigitado: Periodo) {
    const periodo = todos ? {} : periodoDigitado
    confReprocessar.abrirComPrevia(
      async () => {
        const preview = await pedidosApi.previewReprocessarLote({ ...periodo, apenas_erro: apenasErro })
        return { apenasErro, todos, periodo, total: preview.total }
      },
      (e) => flash.erro(apiErr(e, 'Não foi possível calcular quantos pedidos seriam afetados.')),
    )
  }

  function solicitarTransmitirLote(apenasSemOcorrencia: boolean) {
    setTransmitirDialogOpen(false)
    confTransmitirLote.abrirComPrevia(
      async () => {
        const preview = await pedidosApi.previewLoteTransmitir({ apenas_sem_ocorrencia: apenasSemOcorrencia })
        return { apenasSemOcorrencia, total: preview.total }
      },
      (e) => flash.erro(apiErr(e, 'Não foi possível calcular quantos pedidos seriam transmitidos.')),
    )
  }

  async function rodarLote(
    titulo: string,
    fn: () => Promise<LoteResultado>,
    setPending: (v: boolean) => void,
    setResult: (r: LoteEstado | null) => void,
  ) {
    setPending(true)
    setResult(null)
    try {
      setResult({ titulo, resultado: await fn() })
      invalidar()
    } catch (e) {
      setResult({ titulo, erro: apiErr(e, 'A requisição falhou. Nenhuma alteração foi confirmada pelo servidor.') })
    } finally {
      setPending(false)
    }
  }

  const executarReprocessar = ({ apenasErro, periodo }: PedidoReprocessar) =>
    rodarLote(
      'Reprocessamento',
      () => pedidosApi.reprocessarLoteNaoTransmitidos({ ...periodo, apenas_erro: apenasErro }),
      setReprocessarPending,
      setReprocessarResult,
    )

  const executarTransmitirLote = ({ apenasSemOcorrencia }: { apenasSemOcorrencia: boolean }) =>
    rodarLote(
      'Transmissão',
      () => pedidosApi.loteTransmitir({ apenas_sem_ocorrencia: apenasSemOcorrencia }),
      setTransmitirPending,
      setTransmitirResult,
    )

  const reprocessar = useMutation({
    mutationFn: pedidosApi.reprocessar,
    onSuccess: () => { invalidar(); flash.sucesso('Reprocessamento solicitado com sucesso.') },
    onError: (e: unknown) => flash.erro(apiErr(e, 'Erro ao reprocessar.')),
  })

  const transmitirItem = useMutation({
    mutationFn: pedidosApi.transmitir,
    onSuccess: () => { invalidar(); flash.sucesso('Pedido transmitido com sucesso.') },
    onError: (e: unknown) => flash.erro(apiErr(e, 'Erro ao transmitir.')),
  })

  // Handlers estáveis para as linhas memoizadas.
  const onAbrir = useEventCallback((id: number) => navigate(`/pedidos/${id}`))
  const onAlternar = useEventCallback((id: number) => sel.alternar(id))
  const onReprocessarLinha = useEventCallback((id: number) => reprocessar.mutate(id))
  const onTransmitirLinha = useEventCallback((id: number) => solicitarTransmissao([id]))

  const contagem = data?.contagem_por_status ?? {}
  const previewPending = confReprocessar.carregando || confTransmitirLote.carregando
  const anyActionPending =
    emLote !== null || reprocessarPending || transmitirPending ||
    reprocessar.isPending || transmitirItem.isPending || previewPending
  // Enquanto a página nova carrega, as linhas da anterior ficam visíveis mas
  // sem ação — selecionar uma delas não faria sentido na consulta nova.
  const linhasBloqueadas = anyActionPending || isPlaceholderData

  const colunas: Coluna[] = [
    ...(isOperacional ? [{
      key: 'sel',
      className: 'w-8',
      label: (
        <input
          type="checkbox"
          aria-label="Selecionar todos da página"
          checked={sel.todosMarcados}
          onChange={sel.alternarTodos}
          disabled={linhasBloqueadas || items.length === 0}
          className="rounded border-slate-300 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        />
      ),
    }] : []),
    { key: 'pedido', label: 'Pedido OL' },
    { key: 'cnpj', label: 'CNPJ' },
    { key: 'industria', label: 'Indústria' },
    { key: 'data', label: 'Data' },
    { key: 'status', label: 'Status Op.' },
    { key: 'ocorr', label: 'Ocorr.', align: 'center' },
    ...(isOperacional ? [{ key: 'acoes', label: 'Ações', align: 'center' as const }] : []),
    { key: 'chevron' },
  ]

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
        <h1 className="text-xl font-semibold text-slate-800">Triagem</h1>
        <div className="flex items-center gap-2 flex-wrap">
          <IconButton label="Atualizar lista" appearance="outline" onClick={invalidar}>
            <RefreshCw size={15} className={isFetching ? 'animate-spin' : ''} />
          </IconButton>
          {isOperacional && (
            <button
              onClick={() => setShowReprocessar((v) => !v)}
              disabled={anyActionPending}
              aria-expanded={showReprocessar}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors disabled:opacity-50 ${
                showReprocessar
                  ? 'border-amber-400 bg-amber-50 text-amber-700'
                  : 'border-slate-300 bg-white hover:bg-slate-50 text-slate-600'
              }`}
            >
              <RotateCcw size={15} />
              Reprocessar
            </button>
          )}
          {isOperacional && (
            <Button
              variant="primary"
              onClick={() => setTransmitirDialogOpen(true)}
              disabled={anyActionPending}
              loading={transmitirPending}
              icon={<SendHorizontal size={15} />}
            >
              Transmitir
            </Button>
          )}
          <FilterToggleButton {...lf.toggleProps} />
          <Button onClick={() => exportar.mutate()} loading={exportar.isPending} icon={<Download size={15} />}>
            Exportar
          </Button>
        </div>
      </div>

      {envioSomentePronto && (
        <div className="mb-3">
          <Tooltip label='Parâmetro "Bloquear envio de pedidos em Verificar" ligado: pedidos que não estão "Pronto" não podem ser transmitidos.'>
            <span className="inline-flex items-center gap-1.5 text-xs text-slate-600 bg-white border border-slate-200 rounded-full px-3 py-1.5">
              <Lock size={12} className="text-slate-400" />
              Envio manual só para pedidos "Pronto"
            </span>
          </Tooltip>
        </div>
      )}

      {/* Seção única de filtros */}
      <FilterBar {...lf.barProps}>
        <FiltroSelect
          label="Status Operacional"
          value={filters.status_operacional ?? ''}
          onChange={(v) => lf.aplicar({ status_operacional: v || undefined })}
        >
          <option value="">Todos ({Object.values(contagem).reduce((a, b) => a + b, 0)})</option>
          {STATUS_CONFECCAO.map((s) => (
            <option key={s} value={s}>{exibirStatus(s)} ({contagem[s] ?? 0})</option>
          ))}
        </FiltroSelect>
        <FiltroSelect
          label="Analisado"
          value={filters.analisado === undefined ? '' : filters.analisado ? 'sim' : 'nao'}
          onChange={(v) => lf.aplicar({ analisado: v === 'sim' ? true : v === 'nao' ? false : undefined })}
        >
          <option value="">Todos</option>
          <option value="sim">Sim</option>
          <option value="nao">Não</option>
        </FiltroSelect>
      </FilterBar>

      {showReprocessar && isOperacional && (
        <ReprocessarPanel
          disabled={anyActionPending}
          pending={reprocessarPending}
          estado={reprocessarResult}
          onSolicitar={solicitarReprocessar}
        />
      )}

      {/* Resultado: Transmitir */}
      <LoteResultadoPanel
        estado={transmitirResult}
        className="mb-4"
        vazio='Nenhum pedido "Não Transmitido" encontrado para o critério selecionado.'
        descreverSucesso={(r) => `${r.sucesso} de ${r.total} arquivo(s) transmitido(s) com sucesso.`}
        onClose={() => setTransmitirResult(null)}
      />

      <FlashBanner flash={flash.flash} />

      {/* Bulk action bar */}
      {isOperacional && (
        <BulkBar total={sel.total} onLimpar={sel.limpar} disabled={anyActionPending}>
          <button
            onClick={() => confBulkReprocessar.abrir({ ids: sel.ids })}
            disabled={anyActionPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-amber-300 bg-white hover:bg-amber-100 text-amber-700 transition-colors disabled:opacity-50"
          >
            {emLote?.acao === 'reprocessar' ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />} Reprocessar
          </button>
          <button
            onClick={() => solicitarTransmissao(sel.ids)}
            disabled={anyActionPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-green-300 bg-white hover:bg-green-100 text-green-700 transition-colors disabled:opacity-50"
          >
            {emLote?.acao === 'transmitir' ? <Loader2 size={13} className="animate-spin" /> : <SendHorizontal size={13} />} Transmitir
          </button>
        </BulkBar>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200/60 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <TableHead colunas={colunas} />
            <tbody className={`divide-y divide-slate-100 transition-opacity ${isPlaceholderData ? 'opacity-60' : ''}`}>
              <TableFeedback
                colunas={colunas.length}
                isLoading={isLoading}
                isError={isError && !data}
                error={error}
                onRetry={() => refetch()}
                isEmpty={items.length === 0}
                vazio="Nenhum pedido encontrado"
              />
              {items.map((p) => {
                const isSelecionadoEmLote = !!emLote?.ids.has(p.id)
                return (
                  <ConfeccaoRow
                    key={p.id}
                    p={p}
                    isOperacional={isOperacional}
                    selecionado={sel.has(p.id)}
                    bloqueado={linhasBloqueadas}
                    acaoEmAndamento={
                      reprocessar.isPending && reprocessar.variables === p.id ? 'Reprocessando'
                      : transmitirItem.isPending && transmitirItem.variables === p.id ? 'Transmitindo'
                      : isSelecionadoEmLote ? (emLote?.acao === 'transmitir' ? 'Transmitindo' : 'Reprocessando')
                      : null
                    }
                    emLote={isSelecionadoEmLote}
                    envioBloqueado={envioBloqueado(p.status_operacional)}
                    onAbrir={onAbrir}
                    onAlternar={onAlternar}
                    onReprocessar={onReprocessarLinha}
                    onTransmitir={onTransmitirLinha}
                  />
                )
              })}
            </tbody>
          </table>
        </div>
        {data && data.pages > 1 && (
          <Pagination
            page={data.page}
            pages={data.pages}
            total={data.total}
            size={data.size}
            onPageChange={lf.setPage}
          />
        )}
      </div>

      <TransmitirDialog
        open={transmitirDialogOpen}
        somentePronto={envioSomentePronto}
        onConfirm={solicitarTransmitirLote}
        onCancel={() => setTransmitirDialogOpen(false)}
      />

      <ConfirmDialog
        open={confReprocessar.aberto}
        title="Reprocessar pedidos"
        description={
          confReprocessar.valor
            ? `Isso vai reprocessar ${confReprocessar.valor.total} pedido(s)${
                confReprocessar.valor.todos ? ' — todos com Status ERP "Não Transmitido"' : ''
              }. A operação pode demorar alguns instantes. Deseja continuar?`
            : ''
        }
        confirmLabel={confReprocessar.valor ? `Reprocessar ${confReprocessar.valor.total} pedido(s)` : 'Confirmar'}
        onConfirm={confReprocessar.confirmar(executarReprocessar)}
        onCancel={confReprocessar.fechar}
      />

      <ConfirmDialog
        open={confBulkReprocessar.aberto}
        title="Reprocessar selecionados"
        description={`Isso vai reprocessar ${confBulkReprocessar.valor?.ids.length ?? 0} pedido(s) selecionado(s). Deseja continuar?`}
        confirmLabel={`Reprocessar ${confBulkReprocessar.valor?.ids.length ?? 0} pedido(s)`}
        onConfirm={confBulkReprocessar.confirmar(({ ids }) => executarSelecionados('reprocessar', ids))}
        onCancel={confBulkReprocessar.fechar}
      />

      <ConfirmDialog
        open={confTransmitirLote.aberto}
        title="Transmitir arquivos"
        description={
          confTransmitirLote.valor
            ? `Isso vai transmitir ${confTransmitirLote.valor.total} pedido(s)${
                envioSomentePronto
                  ? ' com status "Pronto" (pedidos em "Verificar" ficam de fora)'
                  : confTransmitirLote.valor.apenasSemOcorrencia
                    ? ' sem ocorrências abertas'
                    : ', incluindo os que possuem ocorrências abertas'
              }. Deseja continuar?`
            : ''
        }
        confirmLabel={confTransmitirLote.valor ? `Transmitir ${confTransmitirLote.valor.total} pedido(s)` : 'Confirmar'}
        onConfirm={confTransmitirLote.confirmar(executarTransmitirLote)}
        onCancel={confTransmitirLote.fechar}
      />

      <ConfirmDialog
        open={confTransmitirSel.aberto}
        title="Transmitir pedidos"
        description={
          confTransmitirSel.valor
            ? `Isso vai transmitir ${confTransmitirSel.valor.ids.length} pedido(s)${
                confTransmitirSel.valor.algumComOcorrencia
                  ? '. Atenção: parte deles possui ocorrência(s) aberta(s) não resolvida(s)'
                  : ''
              }${
                confTransmitirSel.valor.ignorados > 0
                  ? `. ${confTransmitirSel.valor.ignorados} pedido(s) selecionado(s) não estão "Pronto" e ficam de fora`
                  : ''
              }. Deseja continuar?`
            : ''
        }
        confirmLabel={
          confTransmitirSel.valor
            ? `Transmitir ${confTransmitirSel.valor.ids.length} pedido(s)`
            : 'Transmitir mesmo assim'
        }
        onConfirm={confTransmitirSel.confirmar(({ ids }) => executarTransmissaoDireta(ids))}
        onCancel={confTransmitirSel.fechar}
      />
    </div>
  )
}

/** Painel "Reprocessar pedidos". As datas ficam no estado deste componente, para
 *  digitar nelas não redesenhar a página inteira (R1). */
function ReprocessarPanel({ disabled, pending, estado, onSolicitar }: {
  disabled: boolean
  pending: boolean
  estado: LoteEstado | null
  onSolicitar: (apenasErro: boolean, todos: boolean, periodo: Periodo) => void
}) {
  const [periodo, setPeriodo] = useState<Periodo>({})
  const icone = (i: React.ReactNode) => (pending ? <Loader2 size={14} className="animate-spin" /> : i)

  return (
    <div className="bg-white rounded-xl border border-amber-200 p-5 mb-4 shadow-sm">
      <p className="text-sm font-semibold text-slate-700 mb-4">Reprocessar pedidos</p>
      <div className="flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Data início</label>
          <input
            type="date"
            value={periodo.data_inicio ?? ''}
            onChange={(e) => setPeriodo((d) => ({ ...d, data_inicio: e.target.value || undefined }))}
            className="px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Data fim</label>
          <input
            type="date"
            value={periodo.data_fim ?? ''}
            onChange={(e) => setPeriodo((d) => ({ ...d, data_fim: e.target.value || undefined }))}
            className="px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => onSolicitar(false, false, periodo)}
            disabled={disabled || !periodo.data_inicio}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-blue-300 bg-blue-50 hover:bg-blue-100 text-blue-700 text-sm font-medium transition-colors disabled:opacity-50"
          >
            {icone(<CalendarRange size={14} />)}
            Por período
          </button>
          <button
            onClick={() => onSolicitar(true, false, periodo)}
            disabled={disabled}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-red-300 bg-red-50 hover:bg-red-100 text-red-700 text-sm font-medium transition-colors disabled:opacity-50"
          >
            {icone(<AlertTriangle size={14} />)}
            Somente com erro
          </button>
          <button
            onClick={() => onSolicitar(false, true, periodo)}
            disabled={disabled}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 hover:bg-slate-100 text-slate-700 text-sm font-medium transition-colors disabled:opacity-50"
          >
            {icone(<RotateCcw size={14} />)}
            Todos
          </button>
        </div>
      </div>

      <LoteResultadoPanel estado={estado} />
    </div>
  )
}

interface ConfeccaoRowProps {
  p: PedidoListItem
  isOperacional: boolean
  selecionado: boolean
  bloqueado: boolean
  acaoEmAndamento: string | null
  emLote: boolean
  envioBloqueado: boolean
  onAbrir: (id: number) => void
  onAlternar: (id: number) => void
  onReprocessar: (id: number) => void
  onTransmitir: (id: number) => void
}

/** Linha da Triagem. Com `memo` + handlers estáveis, só redesenha a linha cujas
 *  props mudaram — o polling e o feedback da página não refazem as 20 linhas
 *  com seus Tooltips (R1). O react-query preserva a identidade de `p` quando o
 *  pedido não mudou entre duas consultas. */
const ConfeccaoRow = memo(function ConfeccaoRow({
  p, isOperacional, selecionado, bloqueado, acaoEmAndamento, emLote, envioBloqueado,
  onAbrir, onAlternar, onReprocessar, onTransmitir,
}: ConfeccaoRowProps) {
  const emAnalise = p.status_operacional === STATUS_EM_ANALISE
  const podeReprocessar = REPROCESSAR_ROW_STATUS.includes(p.status_operacional ?? '')
  const podeTransmitir = PODE_TRANSMITIR_ROW_STATUS.includes(p.status_operacional ?? '')

  return (
    <tr
      className={`hover:bg-slate-50 transition-colors ${LINHA_CLICAVEL_CLASS}`}
      {...linhaClicavel(() => onAbrir(p.id))}
    >
      {isOperacional && (
        <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
          <Tooltip label={emAnalise ? 'Pedido em análise — não pode ser selecionado para ações em lote' : undefined}>
            <input
              type="checkbox"
              aria-label={`Selecionar pedido ${p.numero_pedido_ol}`}
              checked={selecionado}
              disabled={bloqueado || emAnalise}
              onChange={() => onAlternar(p.id)}
              className="rounded border-slate-300 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            />
          </Tooltip>
        </td>
      )}
      <td className="px-4 py-3 font-mono text-xs text-slate-700">{p.numero_pedido_ol}</td>
      <td className="px-4 py-3 font-mono text-xs text-slate-500">{p.cnpj_cliente}</td>
      <td className="px-4 py-3 text-slate-600">{p.industria_nome}</td>
      <td className="px-4 py-3 text-slate-500">{fmtData(p.data_pedido)}</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1.5">
          <StatusBadge status={acaoEmAndamento ?? p.status_operacional} />
          {!!acaoEmAndamento && (
            <Tooltip label={emLote ? `${acaoEmAndamento} em lote…` : undefined}>
              <Loader2 size={12} className="animate-spin text-slate-400" />
            </Tooltip>
          )}
          <AnalisadoBadge por={p.analisado_por} em={p.analisado_em} />
        </div>
        {emAnalise && !acaoEmAndamento && (
          <Tooltip label={p.em_analise_desde ? `Em análise desde ${fmtDataHora(p.em_analise_desde)}` : undefined}>
            <p className="mt-1 inline-flex items-center gap-1 text-xs text-violet-600">
              <UserCheck size={11} />
              por {p.em_analise_por ?? '—'}
            </p>
          </Tooltip>
        )}
      </td>
      <td className="px-4 py-3 text-center">
        {p.total_ocorrencias_abertas > 0 ? (
          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-red-100 text-red-600 text-xs font-bold">
            {p.total_ocorrencias_abertas}
          </span>
        ) : (
          <span className="text-slate-300">—</span>
        )}
      </td>
      {isOperacional && (
        <td className="px-4 py-3 text-center" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-center gap-1">
            {podeReprocessar && (
              <IconButton
                label="Reprocessar"
                onClick={() => onReprocessar(p.id)}
                disabled={bloqueado}
                className="hover:bg-amber-50 hover:text-amber-500"
              >
                <RotateCcw size={14} />
              </IconButton>
            )}
            {podeTransmitir && (
              <IconButton
                label="Transmitir"
                tooltip={envioBloqueado ? MSG_ENVIO_BLOQUEADO : undefined}
                onClick={() => onTransmitir(p.id)}
                disabled={bloqueado || envioBloqueado}
                className={`hover:bg-green-50 hover:text-green-600 ${envioBloqueado ? 'pointer-events-none' : ''}`}
              >
                <SendHorizontal size={14} />
              </IconButton>
            )}
          </div>
        </td>
      )}
      <td className="px-3 py-3 text-slate-300">
        <ChevronRight size={14} />
      </td>
    </tr>
  )
})
