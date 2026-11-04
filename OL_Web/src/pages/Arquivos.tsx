import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { arquivosApi, type ArquivosFilter } from '../api/arquivos'
import StatusBadge from '../components/StatusBadge'
import Pagination from '../components/Pagination'
import FlashBanner from '../components/FlashBanner'
import { Button, IconButton } from '../components/Button'
import { TableHead, TableFeedback, type Coluna } from '../components/Table'
import { useFlash } from '../hooks/useFlash'
import { opcoesLista } from '../lib/queryOpcoes'
import { LINHA_CLICAVEL_CLASS, linhaClicavel } from '../lib/linhaClicavel'
import { fmtDataHoraCurta } from '../lib/format'
import { Search, RefreshCw, Download } from 'lucide-react'

const TIPOS = ['pedido', 'retorno', 'espelho', 'cancelado']
const SITUACOES = ['Verificar', 'Enviado', 'Erro']

const COLUNAS: Coluna[] = [
  { key: 'arquivo', label: 'Arquivo' },
  { key: 'pedido', label: 'Pedido OL' },
  { key: 'tipo', label: 'Tipo' },
  { key: 'situacao', label: 'Situação' },
  { key: 'data', label: 'Data' },
  { key: 'baixar' },
]

export default function Arquivos() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [filters, setFilters] = useState<ArquivosFilter>({ page: 1, size: 30 })
  const [draft, setDraft] = useState<ArquivosFilter>({})
  const [downloading, setDownloading] = useState<number | null>(null)
  const flash = useFlash()

  const { data, isLoading, isFetching, isError, error, refetch, isPlaceholderData } = useQuery({
    queryKey: ['arquivos', filters],
    queryFn: () => arquivosApi.list(filters),
    ...opcoesLista(),
  })

  function apply() { setFilters({ ...draft, page: 1, size: 30 }) }
  function clear() { setDraft({}); setFilters({ page: 1, size: 30 }) }

  async function handleDownload(id: number, nome: string | null) {
    setDownloading(id)
    flash.limpar()
    try {
      await arquivosApi.download(id, nome ?? `arquivo_${id}.txt`)
    } catch {
      flash.erro('Arquivo não encontrado no servidor.')
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-semibold text-slate-800">Arquivos</h1>
        <IconButton label="Atualizar lista" appearance="outline" onClick={() => qc.invalidateQueries({ queryKey: ['arquivos'] })}>
          <RefreshCw size={15} className={isFetching ? 'animate-spin' : ''} />
        </IconButton>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 shadow-sm">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Nome do Arquivo</label>
            <input
              value={draft.nome ?? ''}
              onChange={(e) => setDraft((d) => ({ ...d, nome: e.target.value || undefined }))}
              placeholder="PEDIDO_00000000000000000001_..."
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Número Pedido</label>
            <input
              value={draft.numero_pedido_ol ?? ''}
              onChange={(e) => setDraft((d) => ({ ...d, numero_pedido_ol: e.target.value || undefined }))}
              placeholder="2026…"
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Tipo</label>
            <select
              value={draft.tipo ?? ''}
              onChange={(e) => setDraft((d) => ({ ...d, tipo: e.target.value || undefined }))}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="">Todos</option>
              {TIPOS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Situação</label>
            <select
              value={draft.situacao ?? ''}
              onChange={(e) => setDraft((d) => ({ ...d, situacao: e.target.value || undefined }))}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="">Todas</option>
              {SITUACOES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="flex items-end gap-2">
            <Button variant="primary" onClick={apply} icon={<Search size={14} />}>
              Buscar
            </Button>
            <Button onClick={clear}>Limpar</Button>
          </div>
        </div>
      </div>

      <FlashBanner flash={flash.flash} />

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200/60 overflow-hidden">
        <table className="w-full text-sm">
          <TableHead colunas={COLUNAS} />
          <tbody className={`divide-y divide-slate-100 transition-opacity ${isPlaceholderData ? 'opacity-60' : ''}`}>
            <TableFeedback
              colunas={COLUNAS.length}
              linhas={8}
              isLoading={isLoading}
              isError={isError && !data}
              error={error}
              onRetry={() => refetch()}
              isEmpty={!data?.items.length}
              vazio="Nenhum arquivo encontrado"
            />
            {data?.items.map((a) => (
              <tr
                key={a.id}
                className={a.id_pedido != null ? `hover:bg-slate-50 ${LINHA_CLICAVEL_CLASS}` : ''}
                {...(a.id_pedido != null ? linhaClicavel(() => navigate(`/pedidos/${a.id_pedido}`)) : {})}
              >
                <td className="px-4 py-3 font-medium text-slate-700">{a.nome ?? '—'}</td>
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{a.numero_pedido_ol ?? '—'}</td>
                <td className="px-4 py-3">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 capitalize">
                    {a.tipo ?? '—'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {a.situacao ? <StatusBadge status={a.situacao} /> : <span className="text-slate-300">—</span>}
                </td>
                <td className="px-4 py-3 text-slate-500 text-xs">{fmtDataHoraCurta(a.criado_em)}</td>
                <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                  <Button
                    size="xs"
                    onClick={() => handleDownload(a.id, a.nome)}
                    loading={downloading === a.id}
                    icon={<Download size={12} />}
                  >
                    Baixar
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && data.pages > 1 && (
          <Pagination
            page={data.page} pages={data.pages} total={data.total} size={data.size}
            onPageChange={(p) => setFilters((f) => ({ ...f, page: p }))}
          />
        )}
      </div>
    </div>
  )
}
