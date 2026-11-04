import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { industriasApi, type IndustriaCreate } from '../../api/industrias'
import type { IndustriaListItem } from '../../types'
import { Plus, RefreshCw, X, Factory } from 'lucide-react'
import { apiErr } from '../../lib/apiError'
import { Button, IconButton } from '../../components/Button'
import Modal from '../../components/Modal'
import { LINHA_CLICAVEL_CLASS, linhaClicavel } from '../../lib/linhaClicavel'
import { TableHead, TableFeedback, type Coluna } from '../../components/Table'

const COLUNAS: Coluna[] = [
  { key: 'nome', label: 'Nome' },
  { key: 'cnpj', label: 'CNPJ' },
  { key: 'layout', label: 'Layout' },
  { key: 'ftp', label: 'FTP' },
  { key: 'status', label: 'Status' },
]


const EMPTY_FORM: IndustriaCreate = { nome: '', cnpj: '', layout: '', ativo: true }

export default function IndustriasList() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<IndustriaCreate>(EMPTY_FORM)
  const [err, setErr] = useState('')

  const { data: industrias, isLoading, isFetching, isError, error, refetch } = useQuery<IndustriaListItem[]>({
    queryKey: ['industrias'],
    queryFn: () => industriasApi.list(),
  })

  const createMut = useMutation({
    mutationFn: (d: IndustriaCreate) => industriasApi.create(d),
    onSuccess: (nova) => {
      qc.invalidateQueries({ queryKey: ['industrias'] })
      closeModal()
      navigate(`/industrias/${nova.id}`)
    },
    onError: (e: unknown) => setErr(apiErr(e, 'Erro ao criar indústria.')),
  })

  function openCreate() {
    setForm(EMPTY_FORM)
    setErr('')
    setModalOpen(true)
  }

  function closeModal() {
    setModalOpen(false)
    setErr('')
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    if (!form.nome.trim()) { setErr('Informe o nome da indústria.'); return }
    createMut.mutate(form)
  }

  const lista = industrias ?? []

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-semibold text-slate-800">Indústrias</h1>
        <div className="flex items-center gap-2">
          <IconButton label="Atualizar lista" appearance="outline" onClick={() => qc.invalidateQueries({ queryKey: ['industrias'] })}>
            <RefreshCw size={15} className={isFetching ? 'animate-spin' : ''} />
          </IconButton>
          <Button variant="primary" onClick={openCreate} icon={<Plus size={15} />}>
            Nova Indústria
          </Button>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200/60 overflow-hidden">
        <table className="w-full text-sm">
          <TableHead colunas={COLUNAS} />
          <tbody className="divide-y divide-slate-100">
            <TableFeedback
              colunas={COLUNAS.length}
              linhas={3}
              isLoading={isLoading}
              isError={isError && !industrias}
              error={error}
              onRetry={() => refetch()}
              isEmpty={lista.length === 0}
              vazio="Nenhuma indústria cadastrada."
            />
            {(
              lista.map((ind) => (
                <tr
                  key={ind.id}
                  {...linhaClicavel(() => navigate(`/industrias/${ind.id}`))}
                  className={`hover:bg-slate-50 ${LINHA_CLICAVEL_CLASS}`}
                >
                  <td className="px-4 py-3 font-medium text-slate-800">
                    <div className="flex items-center gap-2">
                      <Factory size={14} className="text-slate-400" />
                      {ind.nome ?? '—'}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{ind.cnpj ?? '—'}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">
                      {ind.layout ?? '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      ind.tem_ftp ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
                    }`}>
                      {ind.tem_ftp ? 'Configurado' : 'Não configurado'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      ind.ativo ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
                    }`}>
                      {ind.ativo ? 'Ativa' : 'Inativa'}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Modal criação */}
      <Modal
        aberto={modalOpen}
        onFechar={closeModal}
        tituloId="nova-industria-titulo"
        fecharNoFundo={false}
        className="max-w-md rounded-2xl shadow-2xl"
        overlayClassName="bg-slate-900/60"
      >
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
              <h2 id="nova-industria-titulo" className="text-base font-semibold text-slate-800">Nova Indústria</h2>
              <IconButton label="Fechar" onClick={closeModal} className="hover:bg-slate-100">
                <X size={18} />
              </IconButton>
            </div>

            <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Nome</label>
                <input
                  value={form.nome}
                  onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))}
                  required
                  autoFocus
                  className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">CNPJ</label>
                <input
                  value={form.cnpj}
                  onChange={(e) => setForm((f) => ({ ...f, cnpj: e.target.value }))}
                  placeholder="Somente números"
                  className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Layout</label>
                <input
                  value={form.layout}
                  onChange={(e) => setForm((f) => ({ ...f, layout: e.target.value }))}
                  placeholder="ex.: closeup"
                  className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {err && (
                <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{err}</p>
              )}

              <p className="text-xs text-slate-400">
                As pastas e o FTP são configurados na tela da indústria, depois de criada.
              </p>

              <div className="flex gap-2 pt-1">
                <Button type="submit" variant="primary" loading={createMut.isPending} className="flex-1">
                  {createMut.isPending ? 'Criando…' : 'Criar'}
                </Button>
                <button
                  type="button"
                  onClick={closeModal}
                  className="flex-1 py-2.5 border border-slate-300 text-slate-600 rounded-lg text-sm hover:bg-slate-50 transition-colors"
                >
                  Cancelar
                </button>
              </div>
            </form>
      </Modal>
    </div>
  )
}
