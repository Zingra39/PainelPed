import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ocorrenciasApi, type OcorrenciasFilter } from '../api/ocorrencias'
import Pagination from '../components/Pagination'
import StatusBadge from '../components/StatusBadge'
import { Button, IconButton } from '../components/Button'
import { TableHead, TableFeedback, type Coluna } from '../components/Table'
import { fmtDataHoraCurta } from '../lib/format'
import { opcoesLista } from '../lib/queryOpcoes'
import { LINHA_CLICAVEL_CLASS, linhaClicavel } from '../lib/linhaClicavel'
import { Search, RefreshCw } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'

const COLUNAS: Coluna[] = [
  { key: 'pedido', label: 'Pedido OL' },
  { key: 'severidade', label: 'Severidade' },
  { key: 'mensagem', label: 'Mensagem' },
  { key: 'data', label: 'Data' },
]

// Taxonomia real de severidade (OL_CORE `TipoSeveridade`) — da mais para a
// menos urgente, para priorizar visualmente na hora de triar as ocorrências.
const SEVERIDADE_OPTIONS = [
  { value: 'CRITICO', label: 'Crítico' },
  { value: 'ERRO', label: 'Erro' },
  { value: 'ALERTA', label: 'Alerta' },
  { value: 'INFO', label: 'Informativo' },
]

export default function Ocorrencias() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  // A tela lista apenas ocorrências em aberto: `resolvido: false` é fixo em
  // toda consulta, e por isso a coluna/filtro de Status saiu — todas as
  // linhas exibidas teriam sempre o mesmo valor ("Aberta").
  const [filters, setFilters] = useState<OcorrenciasFilter>({ resolvido: false, page: 1, size: 30 })
  const [draft, setDraft] = useState<OcorrenciasFilter>({})

  const { data, isLoading, isFetching, isError, error, refetch, isPlaceholderData } = useQuery({
    queryKey: ['ocorrencias', filters],
    queryFn: () => ocorrenciasApi.list(filters),
    ...opcoesLista(),
  })

  function apply() { setFilters({ ...draft, resolvido: false, page: 1, size: 30 }) }
  function clear() { setDraft({}); setFilters({ resolvido: false, page: 1, size: 30 }) }

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">Ocorrências</h1>
          <p className="text-xs text-slate-400 mt-0.5">Somente ocorrências em aberto</p>
        </div>
        <IconButton label="Atualizar lista" appearance="outline" onClick={() => qc.invalidateQueries({ queryKey: ['ocorrencias'] })}>
          <RefreshCw size={15} className={isFetching ? 'animate-spin' : ''} />
        </IconButton>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 shadow-sm">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
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
            <label className="block text-xs font-medium text-slate-600 mb-1">Severidade</label>
            <select
              value={draft.severidade ?? ''}
              onChange={(e) => setDraft((d) => ({ ...d, severidade: e.target.value || undefined }))}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="">Todas</option>
              {SEVERIDADE_OPTIONS.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end gap-2 col-span-2 md:col-span-2">
            <Button variant="primary" onClick={apply} icon={<Search size={14} />}>
              Buscar
            </Button>
            <Button onClick={clear}>Limpar</Button>
          </div>
        </div>
      </div>

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
              vazio="Nenhuma ocorrência em aberto encontrada"
            />
            {data?.items.map((o) => (
              <tr
                key={o.id}
                className={o.id_pedido != null ? `hover:bg-slate-50 ${LINHA_CLICAVEL_CLASS}` : ''}
                {...(o.id_pedido != null ? linhaClicavel(() => navigate(`/pedidos/${o.id_pedido}`)) : {})}
              >
                <td className="px-4 py-3 font-mono text-xs text-slate-600">{o.numero_pedido_ol ?? '—'}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={o.severidade ?? '—'} />
                </td>
                <td className="px-4 py-3 text-slate-700 max-w-sm whitespace-pre-line wrap-break-word">{o.descricao ?? '—'}</td>
                <td className="px-4 py-3 text-slate-500 text-xs">{fmtDataHoraCurta(o.criado_em)}</td>
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
