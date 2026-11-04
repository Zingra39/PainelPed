import { memo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { pedidosApi, type LotePeriodoFilter, type RastreamentoFilter } from '../../api/pedidos'
import { apiErr, apiErrBlob } from '../../lib/apiError'
import type { LoteResultado, PedidoRastreamentoItem } from '../../types'
import Pagination from '../../components/Pagination'
import ConfirmDialog from '../../components/ConfirmDialog'
import StatusBadge from '../../components/StatusBadge'
import { useAuth } from '../../contexts/AuthContext'
import {
  RefreshCw, ChevronRight,
  FileText, Printer, XCircle, Loader2, FilePlus2,
  AlertTriangle, Download,
} from 'lucide-react'
import Tooltip from '../../components/Tooltip'
import AnalisadoBadge from '../../components/AnalisadoBadge'
import FilterBar, { FiltroSelect, FilterToggleButton } from '../../components/FilterBar'
import FlashBanner from '../../components/FlashBanner'
import LoteResultadoPanel, { type LoteEstado } from '../../components/LoteResultadoPanel'
import BulkBar from '../../components/BulkBar'
import { Button, IconButton } from '../../components/Button'
import { TableHead, TableFeedback, type Coluna } from '../../components/Table'
import { fmtData } from '../../lib/format'
import { executarEmLote, resumoLote } from '../../lib/lote'
import { podeGerarCancelamento, podeGerarEspelho, podeGerarRetorno } from '../../lib/statusConfig'
import { useFlash } from '../../hooks/useFlash'
import { useSelecao } from '../../hooks/useSelecao'
import { useConfirmacao } from '../../hooks/useConfirmacao'
import { useListFilters } from '../../hooks/useListFilters'
import { useEventCallback } from '../../hooks/useEventCallback'
import { LINHA_CLICAVEL_CLASS, linhaClicavel } from '../../lib/linhaClicavel'
import { opcoesLista } from '../../lib/queryOpcoes'

const STATUS_RASTREAMENTO = [
  'Gerando Retorno', 'Retorno Gerado', 'Retorno Enviado',
  'Gerando Espelho', 'Espelho Gerado', 'Espelho Enviado',
  'Cancelado', 'Gerando Cancelamento', 'Cancelamento Gerado', 'Cancelamento Enviado',
  'Falha',
]

type TipoLote = 'Retorno' | 'Espelho' | 'Cancelamento'
type TipoSelecao = 'retorno' | 'espelho'

const LOTE: Record<TipoLote, {
  previa: (f: Parameters<typeof pedidosApi.loteRetorno>[0]) => Promise<{ total: number }>
  executar: (f: Parameters<typeof pedidosApi.loteRetorno>[0]) => Promise<LoteResultado>
}> = {
  Retorno:      { previa: pedidosApi.previewLoteRetorno,      executar: pedidosApi.loteRetorno },
  Espelho:      { previa: pedidosApi.previewLoteEspelho,      executar: pedidosApi.loteEspelho },
  Cancelamento: { previa: pedidosApi.previewLoteCancelamento, executar: pedidosApi.loteCancelamento },
}

const SELECAO: Record<TipoSelecao, { label: string; fn: (id: number) => Promise<unknown> }> = {
  retorno: { label: 'Retorno', fn: pedidosApi.gerarRetorno },
  espelho: { label: 'Espelho', fn: pedidosApi.gerarEspelho },
}

export default function Rastreamento() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { isOperacional } = useAuth()
  const flash = useFlash()
  const lf = useListFilters<RastreamentoFilter>({ page: 1, size: 20 })
  const { filters } = lf

  const [bulkActionTipo, setBulkActionTipo] = useState<TipoSelecao | null>(null)

  // Gerar Arquivos (período / todos / por CNPJ)
  const [showGerar, setShowGerar] = useState(false)
  const [gerarPendente, setGerarPendente] = useState<TipoLote | null>(null)
  const [gerarResult, setGerarResult] = useState<LoteEstado | null>(null)
  // O critério (período/CNPJ) vai junto na confirmação: executa exatamente o que foi contado.
  const confGerar = useConfirmacao<{ tipo: TipoLote; filtro: LotePeriodoFilter; total: number }>()
  const confBulkGerar = useConfirmacao<{ tipo: TipoSelecao; ids: number[] }>()

  const { data, isLoading, isFetching, isError, error, refetch, isPlaceholderData } = useQuery({
    queryKey: ['rastreamento', filters],
    queryFn: () => pedidosApi.rastreamentoList(filters),
    // Serviços automáticos (retorno.py e afins) atualizam o status_operacional
    // direto no banco, sem passar por essa tela — sem polling o badge só
    // atualizaria com um refresh manual da página.
    ...opcoesLista(15_000),
  })
  const items = data?.items ?? []
  const invalidar = () => qc.invalidateQueries({ queryKey: ['rastreamento'] })

  const sel = useSelecao(items.map((p) => p.id), filters)
  const numeroDoPedido = (id: number) => items.find((p) => p.id === id)?.numero_pedido_ol ?? String(id)

  const exportar = useMutation({
    mutationFn: () => pedidosApi.exportRastreamento(filters),
    onError: async (e: unknown) => flash.erro(await apiErrBlob(e, 'Não foi possível exportar a planilha.')),
  })

  async function gerarSelecionados({ tipo, ids }: { tipo: TipoSelecao; ids: number[] }) {
    setBulkActionTipo(tipo)
    const res = await executarEmLote(ids, SELECAO[tipo].fn, numeroDoPedido)
    sel.limpar()
    invalidar()
    setBulkActionTipo(null)
    const r = resumoLote(res, `Geração de ${SELECAO[tipo].label.toLowerCase()}`)
    flash.mostrar(r.ok ? 'sucesso' : 'erro', r.texto)
  }

  // Busca quantos pedidos o critério informado afeta (rota de prévia, só
  // leitura) e só então abre a confirmação — a execução real só acontece se
  // o usuário confirmar na tela seguinte.
  function solicitarGerar(tipo: TipoLote, filtro: LotePeriodoFilter) {
    confGerar.abrirComPrevia(
      async () => ({ tipo, filtro, total: (await LOTE[tipo].previa(filtro)).total }),
      (e) => flash.erro(apiErr(e, 'Não foi possível calcular quantos pedidos seriam afetados.')),
    )
  }

  async function executarGerar({ tipo, filtro }: { tipo: TipoLote; filtro: LotePeriodoFilter }) {
    setGerarPendente(tipo)
    setGerarResult(null)
    try {
      setGerarResult({ titulo: tipo, resultado: await LOTE[tipo].executar(filtro) })
      invalidar()
    } catch (e) {
      setGerarResult({ titulo: tipo, erro: apiErr(e, 'A requisição falhou. Nenhuma alteração foi confirmada pelo servidor.') })
    } finally {
      setGerarPendente(null)
    }
  }

  const retorno = useMutation({
    mutationFn: pedidosApi.gerarRetorno,
    onSuccess: () => { invalidar(); flash.sucesso('Retorno realizado com sucesso.') },
    onError: (e: unknown) => flash.erro(apiErr(e, 'Erro ao gerar retorno.')),
  })
  const espelho = useMutation({
    mutationFn: pedidosApi.gerarEspelho,
    onSuccess: () => { invalidar(); flash.sucesso('Espelho realizado com sucesso.') },
    onError: (e: unknown) => flash.erro(apiErr(e, 'Erro ao gerar espelho.')),
  })
  const cancelamento = useMutation({
    mutationFn: pedidosApi.cancelar,
    onSuccess: () => { invalidar(); flash.sucesso('Cancelamento realizado com sucesso.') },
    onError: (e: unknown) => flash.erro(apiErr(e, 'Erro ao registrar cancelamento.')),
  })
  const anyActionPending =
    bulkActionTipo !== null || gerarPendente !== null || confGerar.carregando ||
    retorno.isPending || espelho.isPending || cancelamento.isPending
  // Enquanto a página nova carrega, as linhas da anterior ficam visíveis mas sem ação.
  const linhasBloqueadas = anyActionPending || isPlaceholderData

  // Handlers estáveis para as linhas memoizadas.
  const onAbrir = useEventCallback((id: number) => navigate(`/pedidos/${id}`))
  const onAlternar = useEventCallback((id: number) => sel.alternar(id))
  const onRetorno = useEventCallback((id: number) => retorno.mutate(id))
  const onEspelho = useEventCallback((id: number) => espelho.mutate(id))
  const onCancelamento = useEventCallback((id: number) => cancelamento.mutate(id))

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
    { key: 'retorno', label: 'Retorno' },
    { key: 'espelho', label: 'Espelho' },
    { key: 'cancelamento', label: 'Cancelamento' },
    ...(isOperacional ? [{ key: 'acoes', label: 'Ações', align: 'center' as const }] : []),
    { key: 'chevron' },
  ]

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
        <h1 className="text-xl font-semibold text-slate-800">Rastreamento</h1>
        <div className="flex items-center gap-2 flex-wrap">
          <IconButton label="Atualizar lista" appearance="outline" onClick={invalidar}>
            <RefreshCw size={15} className={isFetching ? 'animate-spin' : ''} />
          </IconButton>
          {isOperacional && (
            <button
              onClick={() => setShowGerar((v) => !v)}
              disabled={anyActionPending}
              aria-expanded={showGerar}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors disabled:opacity-50 ${
                showGerar
                  ? 'border-indigo-400 bg-indigo-50 text-indigo-700'
                  : 'border-slate-300 bg-white hover:bg-slate-50 text-slate-600'
              }`}
            >
              <FilePlus2 size={15} />
              Gerar Arquivos
            </button>
          )}
          <FilterToggleButton {...lf.toggleProps} />
          <Button onClick={() => exportar.mutate()} loading={exportar.isPending} icon={<Download size={15} />}>
            Exportar
          </Button>
        </div>
      </div>

      {/* Seção única de filtros */}
      <FilterBar {...lf.barProps}>
        <FiltroSelect label="Status" value={filters.status ?? ''} onChange={(v) => lf.aplicar({ status: v || undefined })}>
          <option value="">Todos</option>
          {STATUS_RASTREAMENTO.map((s) => <option key={s} value={s}>{s}</option>)}
        </FiltroSelect>
      </FilterBar>

      {showGerar && isOperacional && (
        <GerarArquivosPanel
          disabled={anyActionPending}
          pendente={gerarPendente}
          estado={gerarResult}
          onSolicitar={solicitarGerar}
        />
      )}

      <FlashBanner flash={flash.flash} />

      {/* Bulk action bar: gerar arquivos apenas dos selecionados */}
      {isOperacional && (
        <BulkBar total={sel.total} onLimpar={sel.limpar} disabled={anyActionPending}>
          <button
            onClick={() => confBulkGerar.abrir({ tipo: 'retorno', ids: sel.ids })}
            disabled={anyActionPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-blue-300 bg-white hover:bg-blue-100 text-blue-700 transition-colors disabled:opacity-50"
          >
            {bulkActionTipo === 'retorno' ? <Loader2 size={13} className="animate-spin" /> : <FileText size={13} />} Retorno
          </button>
          <button
            onClick={() => confBulkGerar.abrir({ tipo: 'espelho', ids: sel.ids })}
            disabled={anyActionPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-green-300 bg-white hover:bg-green-100 text-green-700 transition-colors disabled:opacity-50"
          >
            {bulkActionTipo === 'espelho' ? <Loader2 size={13} className="animate-spin" /> : <Printer size={13} />} Espelho
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
              {items.map((p) => (
                <RastreamentoRow
                  key={p.id}
                  p={p}
                  isOperacional={isOperacional}
                  selecionado={sel.has(p.id)}
                  bloqueado={linhasBloqueadas}
                  acaoEmAndamento={
                    retorno.isPending && retorno.variables === p.id ? 'Gerando Retorno' :
                    espelho.isPending && espelho.variables === p.id ? 'Gerando Espelho' :
                    cancelamento.isPending && cancelamento.variables === p.id ? 'Gerando Cancelamento' : null
                  }
                  onAbrir={onAbrir}
                  onAlternar={onAlternar}
                  onRetorno={onRetorno}
                  onEspelho={onEspelho}
                  onCancelamento={onCancelamento}
                />
              ))}
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

      <ConfirmDialog
        open={confGerar.aberto}
        title={`Gerar ${confGerar.valor?.tipo ?? ''} em lote`}
        description={
          confGerar.valor
            ? `Esta ação vai gerar ${confGerar.valor.tipo.toLowerCase()} para ${confGerar.valor.total} pedido(s) que atendem ao critério informado. Deseja continuar?`
            : ''
        }
        confirmLabel={confGerar.valor ? `Gerar para ${confGerar.valor.total} pedido(s)` : 'Confirmar'}
        onConfirm={confGerar.confirmar(executarGerar)}
        onCancel={confGerar.fechar}
      />

      <ConfirmDialog
        open={confBulkGerar.aberto}
        title={`Gerar ${confBulkGerar.valor ? SELECAO[confBulkGerar.valor.tipo].label : ''} dos selecionados`}
        description={
          confBulkGerar.valor
            ? `Isso vai gerar ${SELECAO[confBulkGerar.valor.tipo].label.toLowerCase()} para ${confBulkGerar.valor.ids.length} pedido(s) selecionado(s). Deseja continuar?`
            : ''
        }
        confirmLabel={confBulkGerar.valor ? `Gerar para ${confBulkGerar.valor.ids.length} pedido(s)` : 'Confirmar'}
        onConfirm={confBulkGerar.confirmar(gerarSelecionados)}
        onCancel={confBulkGerar.fechar}
      />
    </div>
  )
}

const BOTOES_GERAR: { tipo: TipoLote; icone: React.ReactNode; cores: string }[] = [
  { tipo: 'Retorno',      icone: <FileText size={14} />, cores: 'border-blue-300 bg-blue-50 hover:bg-blue-100 text-blue-700' },
  { tipo: 'Espelho',      icone: <Printer size={14} />,  cores: 'border-green-300 bg-green-50 hover:bg-green-100 text-green-700' },
  { tipo: 'Cancelamento', icone: <XCircle size={14} />,  cores: 'border-orange-300 bg-orange-50 hover:bg-orange-100 text-orange-700' },
]

/** Painel "Gerar Arquivos". Período e CNPJ ficam no estado deste componente,
 *  para digitar o CNPJ não redesenhar a página inteira (R1). */
function GerarArquivosPanel({ disabled, pendente, estado, onSolicitar }: {
  disabled: boolean
  pendente: TipoLote | null
  estado: LoteEstado | null
  onSolicitar: (tipo: TipoLote, filtro: LotePeriodoFilter) => void
}) {
  const [filtro, setFiltro] = useState<LotePeriodoFilter>({})
  const editar = (campo: keyof LotePeriodoFilter) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setFiltro((d) => ({ ...d, [campo]: e.target.value || undefined }))

  return (
    <div className="bg-white rounded-xl border border-indigo-200 p-5 mb-4 shadow-sm">
      <p className="text-sm font-semibold text-slate-700 mb-1">Gerar Arquivos</p>
      <p className="text-xs text-slate-400 mb-4">
        Deixe os campos em branco para gerar para todos os pedidos. Preencha o período e/ou o CNPJ para restringir.
      </p>
      <div className="flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Data início</label>
          <input
            type="date"
            value={filtro.data_inicio ?? ''}
            onChange={editar('data_inicio')}
            className="px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Data fim</label>
          <input
            type="date"
            value={filtro.data_fim ?? ''}
            onChange={editar('data_fim')}
            className="px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">CNPJ</label>
          <input
            value={filtro.cnpj_cliente ?? ''}
            onChange={editar('cnpj_cliente')}
            placeholder="43410436000161"
            className="px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          {BOTOES_GERAR.map(({ tipo, icone, cores }) => (
            <button
              key={tipo}
              onClick={() => onSolicitar(tipo, filtro)}
              disabled={disabled}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm font-medium transition-colors disabled:opacity-50 ${cores}`}
            >
              {pendente === tipo ? <Loader2 size={14} className="animate-spin" /> : icone}
              {tipo}
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs text-slate-400 mt-3">
        Retorno: pedidos transmitidos/faturados · Espelho: pedidos faturados/transmitidos com NF emitida · Cancelamento: pedidos faturados/transmitidos
      </p>

      <LoteResultadoPanel
        estado={estado}
        descreverSucesso={(r) => r.falha === 0 ? 'Processado com sucesso.' : `Concluído com falhas (${r.sucesso} de ${r.total} com sucesso).`}
      />
    </div>
  )
}

interface RastreamentoRowProps {
  p: PedidoRastreamentoItem
  isOperacional: boolean
  selecionado: boolean
  bloqueado: boolean
  acaoEmAndamento: 'Gerando Retorno' | 'Gerando Espelho' | 'Gerando Cancelamento' | null
  onAbrir: (id: number) => void
  onAlternar: (id: number) => void
  onRetorno: (id: number) => void
  onEspelho: (id: number) => void
  onCancelamento: (id: number) => void
}

/** Linha do Rastreamento, memoizada com handlers estáveis (R1). */
const RastreamentoRow = memo(function RastreamentoRow({
  p, isOperacional, selecionado, bloqueado, acaoEmAndamento,
  onAbrir, onAlternar, onRetorno, onEspelho, onCancelamento,
}: RastreamentoRowProps) {
  return (
    <tr
      className={`hover:bg-slate-50 transition-colors ${LINHA_CLICAVEL_CLASS}`}
      {...linhaClicavel(() => onAbrir(p.id))}
    >
      {isOperacional && (
        <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
          <input
            type="checkbox"
            aria-label={`Selecionar pedido ${p.numero_pedido_ol}`}
            checked={selecionado}
            disabled={bloqueado}
            onChange={() => onAlternar(p.id)}
            className="rounded border-slate-300 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          />
        </td>
      )}
      <td className="px-4 py-3 font-mono text-xs text-slate-700">
        <div className="flex items-center gap-1.5">
          {p.numero_pedido_ol}
          {p.falha_geral && (
            <Tooltip label="Falha no processamento deste pedido">
              <AlertTriangle size={12} className="text-red-500" />
            </Tooltip>
          )}
          <AnalisadoBadge por={p.analisado_por} em={p.analisado_em} />
        </div>
      </td>
      <td className="px-4 py-3 font-mono text-xs text-slate-500">{p.cnpj_cliente}</td>
      <td className="px-4 py-3 text-slate-600">{p.industria_nome}</td>
      <td className="px-4 py-3 text-slate-500">{fmtData(p.data_pedido)}</td>
      <td className="px-4 py-3">
        <StatusBadge status={acaoEmAndamento === 'Gerando Retorno' ? acaoEmAndamento : p.retorno_status} />
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={acaoEmAndamento === 'Gerando Espelho' ? acaoEmAndamento : p.espelho_status} />
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={acaoEmAndamento === 'Gerando Cancelamento' ? acaoEmAndamento : p.cancelamento_status} />
      </td>
      {isOperacional && (
        <td className="px-4 py-3 text-center" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-center gap-1">
            {podeGerarRetorno(p) && (
              <IconButton
                label={p.status_operacional === 'Falha no Retorno' ? 'Tentar gerar Retorno novamente' : p.retorno_manual_liberado ? 'Retorno não gerado há mais de 1h — gerar manualmente' : 'Gerar Retorno'}
                onClick={() => onRetorno(p.id)}
                disabled={bloqueado}
                className="hover:bg-blue-50 hover:text-blue-500"
              >
                <FileText size={14} />
              </IconButton>
            )}
            {podeGerarEspelho(p) && (
              <IconButton
                label={p.status_operacional === 'Falha no Espelho' ? 'Tentar gerar Espelho novamente' : 'Gerar Espelho'}
                onClick={() => onEspelho(p.id)}
                disabled={bloqueado}
                className="hover:bg-green-50 hover:text-green-500"
              >
                <Printer size={14} />
              </IconButton>
            )}
            {podeGerarCancelamento(p) && (
              <IconButton
                label={p.status_operacional === 'Falha no Cancelamento' ? 'Tentar gerar Cancelamento novamente' : 'Gerar Cancelamento'}
                onClick={() => onCancelamento(p.id)}
                disabled={bloqueado}
                className="hover:bg-orange-50 hover:text-orange-500"
              >
                <XCircle size={14} />
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
