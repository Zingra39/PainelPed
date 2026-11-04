import { memo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  pedidosApi, type HistoricoFilter, type ReenvioPeriodo, type ReenvioPreview, type TipoReenvioArquivo,
} from '../../api/pedidos'
import { apiErr, apiErrBlob } from '../../lib/apiError'
import type { LoteResultado, PedidoRastreamentoItem } from '../../types'
import { industriasApi } from '../../api/industrias'
import Pagination from '../../components/Pagination'
import Tooltip from '../../components/Tooltip'
import AnalisadoBadge from '../../components/AnalisadoBadge'
import FilterBar, { FiltroSelect, FilterToggleButton } from '../../components/FilterBar'
import FlashBanner from '../../components/FlashBanner'
import BulkBar from '../../components/BulkBar'
import { Button, IconButton } from '../../components/Button'
import { TableHead, TableFeedback, type Coluna } from '../../components/Table'
import { useAuth } from '../../contexts/AuthContext'
import { fmtData } from '../../lib/format'
import { resumoLote } from '../../lib/lote'
import { useFlash } from '../../hooks/useFlash'
import { useSelecao } from '../../hooks/useSelecao'
import { useConfirmacao } from '../../hooks/useConfirmacao'
import { useListFilters } from '../../hooks/useListFilters'
import { useEventCallback } from '../../hooks/useEventCallback'
import { LINHA_CLICAVEL_CLASS, linhaClicavel } from '../../lib/linhaClicavel'
import { opcoesLista } from '../../lib/queryOpcoes'
import {
  RefreshCw, ChevronRight,
  History, CheckCircle2, XCircle, FileText, Printer, Loader2,
  CalendarRange, Download, AlertCircle,
} from 'lucide-react'
import ConfirmDialog from '../../components/ConfirmDialog'
import Modal from '../../components/Modal'

// Card #57 / revisão do PO — critério de "concluído": o pedido chega a um
// dos dois estágios finais de status_erp (ver TipoStatusErp em OL_CORE):
//   1. "Pedido Concluido" -> Retorno + Espelho gerados (pedido faturado)
//   2. "Pedido Cancelado"   -> Retorno + Cancelamento gerados
// Isso agora é gravado direto na coluna status_erp pelos services de
// geração (ver retorno/espelho/cancelamento_service.py) — o backend filtra
// por essa coluna (indexada) em `/pedidos/historico`, com paginação real de
// servidor. Antes, esta tela reaproveitava /pedidos/rastreamento buscando
// um teto fixo de linhas mais recentes e classificando "concluído" no
// cliente — o que fazia pedidos concluídos há mais tempo somem da lista
// conforme o volume de pedidos ativos crescia (card reportado pelo PO).
type Categoria = 'sucesso' | 'cancelado'

const STATUS_ERP_POR_CATEGORIA: Record<Categoria, string> = {
  sucesso: 'Pedido Concluido',
  cancelado: 'Pedido Cancelado',
}

const CATEGORIA_INFO: Record<Categoria, { label: string; cor: string; icone: React.ReactNode }> = {
  sucesso:   { label: 'Atendido com sucesso', cor: 'bg-green-100 text-green-700',   icone: <CheckCircle2 size={12} /> },
  cancelado: { label: 'Cancelado',            cor: 'bg-orange-100 text-orange-700', icone: <XCircle size={12} /> },
}

function categoriaDoStatusErp(statusErp: string): Categoria | null {
  if (statusErp === STATUS_ERP_POR_CATEGORIA.sucesso) return 'sucesso'
  if (statusErp === STATUS_ERP_POR_CATEGORIA.cancelado) return 'cancelado'
  return null
}

function CategoriaBadge({ categoria }: { categoria: Categoria }) {
  const info = CATEGORIA_INFO[categoria]
  return (
    <span className={`inline-flex items-center gap-1 font-medium rounded-full whitespace-nowrap px-2 py-0.5 text-xs ${info.cor}`}>
      {info.icone}
      {info.label}
    </span>
  )
}

// Esta tela é de REENVIO, não de geração: a ação entrega de novo o mesmo
// arquivo que a indústria já recebeu (o backend lê o caminho gravado em
// `arquivo`), sem regerar conteúdo e sem alterar o status do pedido.
//
// Um tipo só é oferecido quando o pedido de fato tem aquele arquivo — o que a
// listagem informa por `retorno_status` / `espelho_status` /
// `cancelamento_status`.
type TipoReenvio = TipoReenvioArquivo

const REENVIO_INFO: Record<TipoReenvio, { label: string; icone: React.ReactNode; classe: string }> = {
  retorno:      { label: 'Retorno',      icone: <FileText size={13} />, classe: 'border-blue-300 text-blue-700 hover:bg-blue-50' },
  espelho:      { label: 'Espelho',      icone: <Printer size={13} />,  classe: 'border-green-300 text-green-700 hover:bg-green-50' },
  cancelamento: { label: 'Cancelamento', icone: <XCircle size={13} />,  classe: 'border-orange-300 text-orange-700 hover:bg-orange-50' },
}
const TIPOS_REENVIO = Object.keys(REENVIO_INFO) as TipoReenvio[]

function temArquivo(p: PedidoRastreamentoItem, tipo: TipoReenvio): boolean {
  if (tipo === 'retorno') return !!p.retorno_status
  if (tipo === 'espelho') return !!p.espelho_status
  return !!p.cancelamento_status
}

const PAGE_SIZE = 20

export default function Historico() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { isOperacional } = useAuth()
  const flash = useFlash()
  const lf = useListFilters<HistoricoFilter>({ page: 1, size: PAGE_SIZE })
  const { filters } = lf

  const { data: industrias } = useQuery({
    queryKey: ['industrias', 'ativas'],
    queryFn: () => industriasApi.list({ ativo: true }),
  })

  const { data, isLoading, isFetching, isError, error, refetch, isPlaceholderData } = useQuery({
    queryKey: ['historico', filters],
    queryFn: () => pedidosApi.historicoList(filters),
    ...opcoesLista(),
  })

  const items = data?.items ?? []
  const sel = useSelecao(items.map((p) => p.id), filters)

  // Mesmo resumo para o reenvio dos selecionados e para o reenvio por período.
  function relatarLote(res: LoteResultado, tipo: TipoReenvio) {
    qc.invalidateQueries({ queryKey: ['historico'] })
    sel.limpar()
    const r = resumoLote(res, `Reenvio de ${REENVIO_INFO[tipo].label.toLowerCase()}`)
    flash.mostrar(r.ok ? 'sucesso' : 'erro', r.texto)
  }

  const reenviar = useMutation({
    mutationFn: ({ ids, tipo }: { ids: number[]; tipo: TipoReenvio }) => pedidosApi.reenviarLote(ids, tipo),
    onSuccess: (res, { tipo }) => relatarLote(res, tipo),
    onError: (e: unknown) => flash.erro(apiErr(e, 'Erro ao reenviar os arquivos.')),
  })
  // Reenvio por período: as datas ficam no painel (ReenvioPeriodoPanel), para
  // digitar nelas não redesenhar a página (R1). Indústria e situação saem dos
  // filtros JÁ aplicados na tela — são os que o operador está enxergando, e o
  // painel diz isso em texto para não haver surpresa sobre o recorte.
  // O período vai junto na confirmação: executa exatamente o que foi contado.
  const confirmacao = useConfirmacao<{ preview: ReenvioPreview; tipo: TipoReenvio; periodo: ReenvioPeriodo }>()

  // Export: o período é obrigatório (o backend recusa sem ele), então a tela
  // pergunta antes de baixar em vez de mandar um pedido que já nasce 422.
  const [exportAberto, setExportAberto] = useState(false)

  const exportar = useMutation({
    mutationFn: ({ data_inicio, data_fim }: { data_inicio: string; data_fim: string }) =>
      pedidosApi.exportHistorico({ ...filters, data_inicio, data_fim }),
    onSuccess: () => setExportAberto(false),
    onError: async (e: unknown) =>
      flash.erro(await apiErrBlob(e, 'Não foi possível gerar a planilha.')),
  })

  const comFiltrosDaTela = (datas: { data_inicio?: string; data_fim?: string }): ReenvioPeriodo => ({
    ...datas,
    industria_nome: filters.industria_nome,
    status_erp: filters.status_erp,
  })

  // Conta antes de enviar: reenvio escreve em pasta de indústria e dispara
  // FTP, então o operador confirma o volume — e o teto (parâmetro
  // `limitador_de_envio`) barra o disparo aqui, antes da requisição longa.
  const previewPeriodo = useMutation({
    mutationFn: ({ tipo, periodo }: { tipo: TipoReenvio; periodo: ReenvioPeriodo }) => pedidosApi.previewReenvio(periodo, tipo),
    onSuccess: (p, { tipo, periodo }) => {
      const rotulo = REENVIO_INFO[tipo].label.toLowerCase()
      if (p.total === 0) {
        flash.erro(`Nenhum pedido com arquivo de ${rotulo} gerado no período selecionado.`)
      } else if (p.excede) {
        flash.erro(`O período tem ${p.total} pedidos com ${rotulo}, acima do limite de ${p.limite} por reenvio. Estreite o período ou ajuste o limitador na tela de Parametrização.`)
      } else {
        confirmacao.abrir({ preview: p, tipo, periodo })
      }
    },
    onError: (e: unknown) => flash.erro(apiErr(e, 'Não foi possível contar os pedidos do período.')),
  })

  const reenviarPeriodo = useMutation({
    mutationFn: ({ tipo, periodo }: { tipo: TipoReenvio; periodo: ReenvioPeriodo }) => pedidosApi.reenviarPeriodo(periodo, tipo),
    onSuccess: (res, { tipo }) => relatarLote(res, tipo),
    onError: (e: unknown) => flash.erro(apiErr(e, 'Erro ao reenviar os arquivos do período.')),
  })

  const anyActionPending = reenviar.isPending || previewPeriodo.isPending || reenviarPeriodo.isPending
  // Enquanto a página nova carrega, as linhas da anterior ficam visíveis mas sem ação.
  const linhasBloqueadas = anyActionPending || isPlaceholderData
  const tipoPeriodoEmAndamento = previewPeriodo.isPending
    ? previewPeriodo.variables?.tipo
    : reenviarPeriodo.isPending ? reenviarPeriodo.variables?.tipo : undefined

  // Handlers estáveis para as linhas memoizadas.
  const onAbrir = useEventCallback((id: number) => navigate(`/pedidos/${id}`))
  const onAlternar = useEventCallback((id: number) => sel.alternar(id))
  const onReenviarLinha = useEventCallback((id: number, tipo: TipoReenvio) => reenviar.mutate({ ids: [id], tipo }))

  // Tipos oferecidos na barra de ações: só os que existem em TODOS os pedidos
  // selecionados — evita disparar um lote que já nasce com falhas garantidas.
  const selecionados = items.filter((p) => sel.has(p.id))
  const tiposDisponiveis = TIPOS_REENVIO.filter(
    (tipo) => selecionados.length > 0 && selecionados.every((p) => temArquivo(p, tipo)),
  )

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
          className="rounded border-slate-300 cursor-pointer disabled:opacity-40"
        />
      ),
    }] : []),
    { key: 'pedido', label: 'Pedido OL' },
    { key: 'cnpj', label: 'CNPJ' },
    { key: 'industria', label: 'Indústria' },
    { key: 'data', label: 'Data do Pedido' },
    { key: 'situacao', label: 'Situação' },
    { key: 'motivo', label: 'Motivo do Cancelamento' },
    ...(isOperacional ? [{ key: 'reenviar', label: 'Reenviar', align: 'center' as const }] : []),
    { key: 'chevron' },
  ]

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <History size={18} className="text-slate-400" />
          <h1 className="text-xl font-semibold text-slate-800">Histórico de Pedidos</h1>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <IconButton label="Atualizar lista" appearance="outline" onClick={() => qc.invalidateQueries({ queryKey: ['historico'] })}>
            <RefreshCw size={15} className={isFetching ? 'animate-spin' : ''} />
          </IconButton>
          <Button onClick={() => setExportAberto(true)} icon={<Download size={15} />}>
            Exportar Planilha
          </Button>
          <FilterToggleButton {...lf.toggleProps} />
        </div>
      </div>

      <p className="text-xs text-slate-400 mb-4 -mt-3">
        Pedidos com o fluxo encerrado: Pedido Concluído (Retorno + Espelho gerados, pedido faturado) ou Pedido Cancelado (Retorno + Cancelamento gerados). Tela somente leitura — para baixar os arquivos, abra o pedido.
      </p>

      {/* Seção única de filtros */}
      <FilterBar {...lf.barProps}>
        {industrias && industrias.length > 0 && (
          <FiltroSelect
            label="Indústria"
            value={filters.industria_nome ?? ''}
            onChange={(v) => lf.aplicar({ industria_nome: v || undefined })}
          >
            <option value="">Todas</option>
            {industrias.map((i) => i.nome && <option key={i.id} value={i.nome}>{i.nome}</option>)}
          </FiltroSelect>
        )}
        <FiltroSelect
          label="Situação"
          value={filters.status_erp ? (categoriaDoStatusErp(filters.status_erp) ?? '') : ''}
          onChange={(v) => lf.aplicar({ status_erp: v ? STATUS_ERP_POR_CATEGORIA[v as Categoria] : undefined })}
        >
          <option value="">Todas</option>
          <option value="sucesso">Atendido com sucesso</option>
          <option value="cancelado">Cancelado</option>
        </FiltroSelect>
      </FilterBar>

      {isOperacional && (
        <ReenvioPeriodoPanel
          filtrosAplicados={[filters.industria_nome, filters.status_erp].filter(Boolean).join(' · ')}
          disabled={anyActionPending}
          tipoEmAndamento={tipoPeriodoEmAndamento}
          onReenviar={(tipo, datas) => previewPeriodo.mutate({ tipo, periodo: comFiltrosDaTela(datas) })}
        />
      )}

      <FlashBanner flash={flash.flash} />

      {/* Barra de reenvio em massa */}
      {isOperacional && (
        <BulkBar total={sel.total} onLimpar={sel.limpar} disabled={anyActionPending} tom="slate">
          <span className="text-xs text-slate-400">Reenviar arquivo:</span>
          {tiposDisponiveis.length === 0 ? (
            <span className="text-xs text-amber-600">
              Os pedidos selecionados não têm um mesmo tipo de arquivo em comum.
            </span>
          ) : (
            tiposDisponiveis.map((tipo) => (
              <button
                key={tipo}
                onClick={() => reenviar.mutate({ ids: sel.ids, tipo })}
                disabled={anyActionPending}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border bg-white transition-colors disabled:opacity-50 ${REENVIO_INFO[tipo].classe}`}
              >
                {reenviar.isPending && reenviar.variables?.tipo === tipo
                  ? <Loader2 size={13} className="animate-spin" />
                  : REENVIO_INFO[tipo].icone}
                {REENVIO_INFO[tipo].label}
              </button>
            ))
          )}
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
                vazio="Nenhum pedido concluído encontrado para os filtros aplicados"
              />
              {items.map((p) => (
                <HistoricoRow
                  key={p.id}
                  p={p}
                  isOperacional={isOperacional}
                  selecionado={sel.has(p.id)}
                  bloqueado={linhasBloqueadas}
                  tipoReenviando={
                    reenviar.isPending && reenviar.variables?.ids.length === 1 && reenviar.variables.ids[0] === p.id
                      ? reenviar.variables.tipo
                      : undefined
                  }
                  onAbrir={onAbrir}
                  onAlternar={onAlternar}
                  onReenviar={onReenviarLinha}
                />
              ))}
            </tbody>
          </table>
        </div>
        {data && data.total > 0 && (
          <Pagination
            page={data.page}
            pages={data.pages}
            total={data.total}
            size={PAGE_SIZE}
            onPageChange={lf.setPage}
          />
        )}
      </div>

      {/* Export pede o período antes de baixar — obrigatório no backend. */}
      {exportAberto && (
        <ExportarHistoricoDialog
          inicial={{ data_inicio: filters.data_inicio ?? '', data_fim: filters.data_fim ?? '' }}
          pendente={exportar.isPending}
          onExportar={(datas) => exportar.mutate(datas)}
          onFechar={() => setExportAberto(false)}
        />
      )}

      <ConfirmDialog
        open={confirmacao.aberto}
        title={confirmacao.valor ? `Reenviar ${REENVIO_INFO[confirmacao.valor.tipo].label.toLowerCase()} do período?` : ''}
        description={
          confirmacao.valor
            ? `${confirmacao.valor.preview.total} pedido(s) terão o arquivo de ${REENVIO_INFO[confirmacao.valor.tipo].label.toLowerCase()} reenviado para a pasta da indústria e para o FTP. Nenhum outro tipo de arquivo é enviado. O conteúdo é o mesmo já entregue antes — nada é gerado e nenhum status muda. Limite atual: ${confirmacao.valor.preview.limite} pedidos por reenvio.`
            : undefined
        }
        confirmLabel="Reenviar"
        variant="primary"
        onConfirm={confirmacao.confirmar(({ tipo, periodo }) => reenviarPeriodo.mutate({ tipo, periodo }))}
        onCancel={confirmacao.fechar}
      />
    </div>
  )
}

/** Reenvio por período — reenvia, de um tipo só, o arquivo que cada pedido da
 *  janela tiver guardado. Não gera nada: o fluxo destes pedidos já encerrou, os
 *  arquivos existem, isto só entrega de novo. As datas ficam aqui (R1). */
function ReenvioPeriodoPanel({ filtrosAplicados, disabled, tipoEmAndamento, onReenviar }: {
  /** Indústria/situação já filtradas na tela, que o reenvio respeita. */
  filtrosAplicados: string
  disabled: boolean
  tipoEmAndamento?: TipoReenvio
  onReenviar: (tipo: TipoReenvio, datas: { data_inicio?: string; data_fim?: string }) => void
}) {
  const [ini, setIni] = useState('')
  const [fim, setFim] = useState('')
  const semData = !ini && !fim

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <CalendarRange size={15} className="text-slate-400" />
        <p className="text-sm font-semibold text-slate-800">Reenviar arquivos por período</p>
      </div>
      <p className="text-xs text-slate-500 mb-3 max-w-3xl">
        Escolha o período e <strong>um</strong> tipo de arquivo: só ele é reenviado, para
        todos os pedidos do período que o tiverem. Nenhum arquivo é gerado e nenhum status
        muda — é a mesma entrega que a indústria já recebeu.
        {filtrosAplicados && (
          <>
            {' '}Respeita os filtros aplicados agora:{' '}
            <strong className="text-slate-700 font-medium">{filtrosAplicados}</strong>.
          </>
        )}
      </p>
      <div className="flex items-end gap-3 flex-wrap">
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">De</label>
          <input
            type="date"
            value={ini}
            onChange={(e) => setIni(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Até</label>
          <input
            type="date"
            value={fim}
            onChange={(e) => setFim(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="flex items-end gap-2 flex-wrap">
          <span className="text-xs text-slate-400 pb-2.5">Reenviar:</span>
          {TIPOS_REENVIO.map((tipo) => (
            <Tooltip
              key={tipo}
              label={semData ? 'Informe ao menos uma data' : `Reenviar ${REENVIO_INFO[tipo].label.toLowerCase()} de todos os pedidos do período`}
            >
              <button
                onClick={() => onReenviar(tipo, { data_inicio: ini || undefined, data_fim: fim || undefined })}
                disabled={disabled || semData}
                className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg border bg-white text-sm font-medium transition-colors disabled:opacity-50 ${REENVIO_INFO[tipo].classe}`}
              >
                {tipoEmAndamento === tipo
                  ? <Loader2 size={14} className="animate-spin" />
                  : REENVIO_INFO[tipo].icone}
                {REENVIO_INFO[tipo].label}
              </button>
            </Tooltip>
          ))}
        </div>
      </div>
    </div>
  )
}

/** Diálogo de export com as datas próprias (R1). Pré-preenche com o período já
 *  filtrado na tela, quando houver. */
function ExportarHistoricoDialog({ inicial, pendente, onExportar, onFechar }: {
  inicial: { data_inicio: string; data_fim: string }
  pendente: boolean
  onExportar: (datas: { data_inicio: string; data_fim: string }) => void
  onFechar: () => void
}) {
  const [ini, setIni] = useState(inicial.data_inicio)
  const [fim, setFim] = useState(inicial.data_fim)
  const periodoInvalido = !!ini && !!fim && fim < ini

  return (
    <Modal
      aberto
      onFechar={onFechar}
      bloquearFechar={pendente}
      tituloId="export-historico-titulo"
      className="max-w-md p-6 rounded-xl shadow-lg"
    >
        <h2 id="export-historico-titulo" className="text-base font-semibold text-slate-800 mb-1">Exportar planilha</h2>
        <p className="text-sm text-slate-500 mb-4">
          Informe o período dos pedidos (pela data do pedido). A planilha sai com os mesmos
          filtros aplicados na tela.
        </p>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">De</label>
            <input
              type="date"
              value={ini}
              onChange={(e) => setIni(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Até</label>
            <input
              type="date"
              value={fim}
              onChange={(e) => setFim(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {periodoInvalido && (
          <p className="mt-2 text-xs text-red-600">
            A data final não pode ser anterior à inicial.
          </p>
        )}

        <div className="flex gap-3 justify-end mt-5">
          <Button onClick={onFechar} disabled={pendente}>
            Cancelar
          </Button>
          <Button
            variant="primary"
            onClick={() => onExportar({ data_inicio: ini, data_fim: fim })}
            disabled={!ini || !fim || periodoInvalido}
            loading={pendente}
            icon={<Download size={14} />}
          >
            Exportar
          </Button>
        </div>
    </Modal>
  )
}

interface HistoricoRowProps {
  p: PedidoRastreamentoItem
  isOperacional: boolean
  selecionado: boolean
  bloqueado: boolean
  /** Tipo sendo reenviado só para esta linha (spinner no botão). */
  tipoReenviando?: TipoReenvio
  onAbrir: (id: number) => void
  onAlternar: (id: number) => void
  onReenviar: (id: number, tipo: TipoReenvio) => void
}

/** Linha do Histórico, memoizada com handlers estáveis (R1). */
const HistoricoRow = memo(function HistoricoRow({
  p, isOperacional, selecionado, bloqueado, tipoReenviando, onAbrir, onAlternar, onReenviar,
}: HistoricoRowProps) {
  const cat = categoriaDoStatusErp(p.status_erp)
  const tiposDaLinha = TIPOS_REENVIO.filter((t) => temArquivo(p, t))
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
            className="rounded border-slate-300 cursor-pointer disabled:opacity-40"
          />
        </td>
      )}
      <td className="px-4 py-3 font-mono text-xs text-slate-700">
        <div className="flex items-center gap-1.5">
          {p.numero_pedido_ol}
          <AnalisadoBadge por={p.analisado_por} em={p.analisado_em} />
        </div>
      </td>
      <td className="px-4 py-3 font-mono text-xs text-slate-500">{p.cnpj_cliente}</td>
      <td className="px-4 py-3 text-slate-600">{p.industria_nome}</td>
      <td className="px-4 py-3 text-slate-500">{fmtData(p.data_pedido)}</td>
      <td className="px-4 py-3">
        {cat ? <CategoriaBadge categoria={cat} /> : <span className="text-slate-300 text-xs">—</span>}
      </td>
      {/* Motivo vem do ERP e pode ser longo (longtext): trunca na célula e
          mostra inteiro no tooltip, para a linha não esticar a tabela.
          Destacado em laranja — a mesma cor do badge "Cancelado" —, porque é a
          informação que o operador vem procurar nesta tela. Pedido concluído
          não tem motivo: o traço aqui é o estado correto, não um dado faltando. */}
      <td className="px-4 py-3 max-w-[280px]">
        {p.motivo_cancelamento ? (
          <Tooltip label={p.motivo_cancelamento}>
            <span className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-orange-200 bg-orange-50 px-2 py-1 text-xs font-semibold text-orange-800">
              <AlertCircle size={13} className="shrink-0 text-orange-500" />
              <span className="truncate">{p.motivo_cancelamento}</span>
            </span>
          </Tooltip>
        ) : (
          <span className="text-slate-300 text-xs">—</span>
        )}
      </td>
      {isOperacional && (
        <td className="px-4 py-3 text-center" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-center gap-1">
            {tiposDaLinha.length === 0 ? (
              <span className="text-slate-300 text-xs">—</span>
            ) : (
              tiposDaLinha.map((tipo) => (
                <IconButton
                  key={tipo}
                  label={`Reenviar ${REENVIO_INFO[tipo].label}`}
                  onClick={() => onReenviar(p.id, tipo)}
                  disabled={bloqueado}
                  loading={tipoReenviando === tipo}
                  className="hover:bg-slate-100 hover:text-slate-700"
                >
                  {REENVIO_INFO[tipo].icone}
                </IconButton>
              ))
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
