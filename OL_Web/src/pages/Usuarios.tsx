import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { usuariosApi, type CreateUsuario, type UpdateUsuario } from '../api/usuarios'
import type { PaginatedResponse, Usuario } from '../types'
import { Plus, Pencil, UserX, Trash2, RefreshCw, X, Search } from 'lucide-react'
import { apiErr } from '../lib/apiError'
import { fmtData } from '../lib/format'
import Modal from '../components/Modal'
import ConfirmDialog from '../components/ConfirmDialog'
import { Button, IconButton } from '../components/Button'
import { TableHead, TableFeedback, type Coluna } from '../components/Table'

const COLUNAS: Coluna[] = [
  { key: 'nome', label: 'Nome' },
  { key: 'email', label: 'E-mail' },
  { key: 'perfil', label: 'Perfil' },
  { key: 'status', label: 'Status' },
  { key: 'desde', label: 'Desde' },
  { key: 'acoes', label: 'Ações', align: 'center' },
]

const EMPTY_FORM: CreateUsuario = { nome: '', email: '', senha: '', id_perfil: 0 }

export default function Usuarios() {
  const qc = useQueryClient()
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Usuario | null>(null)
  const [form, setForm] = useState<CreateUsuario>(EMPTY_FORM)
  const [err, setErr] = useState('')

  const [busca, setBusca] = useState('')
  const [perfilFiltro, setPerfilFiltro] = useState<number | ''>('')
  const [excluindo, setExcluindo] = useState<Usuario | null>(null)
  const [deleteErr, setDeleteErr] = useState('')
  const [desativando, setDesativando] = useState<Usuario | null>(null)
  const [deactivateErr, setDeactivateErr] = useState('')

  const { data: perfis } = useQuery({
    queryKey: ['perfis'],
    queryFn: usuariosApi.perfis,
  })

  const { data, isLoading, isFetching, isError, error, refetch } = useQuery<PaginatedResponse<Usuario>>({
    queryKey: ['usuarios', busca, perfilFiltro],
    queryFn: () =>
      usuariosApi.list({
        nome: busca || undefined,
        id_perfil: perfilFiltro || undefined,
      }),
  })

  const createMut = useMutation({
    mutationFn: (d: CreateUsuario) => usuariosApi.create(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['usuarios'] }); closeModal() },
    onError: (e: unknown) => setErr(apiErr(e, 'Erro ao criar usuário.')),
  })
  const updateMut = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: UpdateUsuario }) =>
      usuariosApi.update(id, payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['usuarios'] }); closeModal() },
    onError: (e: unknown) => setErr(apiErr(e, 'Erro ao atualizar usuário.')),
  })
  const deactivateMut = useMutation({
    mutationFn: (id: number) => usuariosApi.deactivate(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['usuarios'] })
      setDesativando(null)
      setDeactivateErr('')
    },
    onError: (e: unknown) => setDeactivateErr(apiErr(e, 'Erro ao desativar usuário.')),
  })
  const deleteMut = useMutation({
    mutationFn: (id: number) => usuariosApi.deletePermanent(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['usuarios'] })
      setExcluindo(null)
      setDeleteErr('')
    },
    onError: (e: unknown) => setDeleteErr(apiErr(e, 'Erro ao excluir usuário.')),
  })

  function openCreate() {
    setEditing(null)
    setForm(EMPTY_FORM)
    setErr('')
    setModalOpen(true)
  }

  function openEdit(u: Usuario) {
    setEditing(u)
    setForm({ nome: u.nome ?? '', email: u.email ?? '', senha: '', id_perfil: u.id_perfil ?? 0 })
    setErr('')
    setModalOpen(true)
  }

  function closeModal() {
    setModalOpen(false)
    setEditing(null)
    setErr('')
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    if (editing) {
      const payload: UpdateUsuario = { nome: form.nome, email: form.email, id_perfil: form.id_perfil }
      if (form.senha) payload.senha = form.senha
      updateMut.mutate({ id: editing.id, payload })
    } else {
      if (!form.id_perfil) { setErr('Selecione um perfil.'); return }
      createMut.mutate(form)
    }
  }

  const saving = createMut.isPending || updateMut.isPending
  const usuarios = data?.items ?? []

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-semibold text-slate-800">Usuários</h1>
        <div className="flex items-center gap-2">
          <IconButton label="Atualizar lista" appearance="outline" onClick={() => qc.invalidateQueries({ queryKey: ['usuarios'] })}>
            <RefreshCw size={15} className={isFetching ? 'animate-spin' : ''} />
          </IconButton>
          <Button variant="primary" onClick={openCreate} icon={<Plus size={15} />}>
            Novo Usuário
          </Button>
        </div>
      </div>

      {/* Filtros */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por nome..."
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {busca && (
            <button
              onClick={() => setBusca('')}
              aria-label="Limpar busca"
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <X size={13} />
            </button>
          )}
        </div>
        <select
          value={perfilFiltro}
          onChange={(e) => setPerfilFiltro(e.target.value ? Number(e.target.value) : '')}
          className="px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Todos os perfis</option>
          {perfis?.map((p) => (
            <option key={p.id} value={p.id}>{p.nome}</option>
          ))}
        </select>
        {(busca || perfilFiltro !== '') && (
          <button
            onClick={() => { setBusca(''); setPerfilFiltro('') }}
            className="text-xs text-slate-500 hover:text-slate-700 underline"
          >
            Limpar filtros
          </button>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200/60 overflow-hidden">
        <table className="w-full text-sm">
          <TableHead colunas={COLUNAS} />
          <tbody className="divide-y divide-slate-100">
            <TableFeedback
              colunas={COLUNAS.length}
              linhas={4}
              isLoading={isLoading}
              isError={isError && !data}
              error={error}
              onRetry={() => refetch()}
              isEmpty={usuarios.length === 0}
              vazio={busca || perfilFiltro !== ''
                ? 'Nenhum usuário encontrado com esses filtros.'
                : 'Nenhum usuário cadastrado.'}
            />
            {(
              usuarios.map((u) => (
                <tr key={u.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-800">{u.nome ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-500">{u.email ?? '—'}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">
                      {u.perfil_nome ?? '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      u.ativo ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
                    }`}>
                      {u.ativo ? 'Ativo' : 'Inativo'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs">{fmtData(u.criado_em)}</td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <IconButton label="Editar" onClick={() => openEdit(u)} className="hover:bg-blue-50 hover:text-blue-500">
                        <Pencil size={14} />
                      </IconButton>
                      {u.ativo && (
                        <IconButton
                          label="Desativar"
                          onClick={() => { setDeactivateErr(''); setDesativando(u) }}
                          className="hover:bg-red-50 hover:text-red-500"
                        >
                          <UserX size={14} />
                        </IconButton>
                      )}
                      <IconButton
                        label="Excluir"
                        onClick={() => { setDeleteErr(''); setExcluindo(u) }}
                        className="hover:bg-red-50 hover:text-red-500"
                      >
                        <Trash2 size={14} />
                      </IconButton>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Modal */}
      <Modal
        aberto={modalOpen}
        onFechar={closeModal}
        tituloId="usuario-form-titulo"
        fecharNoFundo={false}
        className="max-w-md rounded-2xl shadow-2xl"
        overlayClassName="bg-slate-900/60"
      >
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
              <h2 id="usuario-form-titulo" className="text-base font-semibold text-slate-800">
                {editing ? 'Editar Usuário' : 'Novo Usuário'}
              </h2>
              <IconButton label="Fechar" onClick={closeModal} className="hover:bg-slate-100">
                <X size={18} />
              </IconButton>
            </div>

            <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Nome completo</label>
                <input
                  value={form.nome}
                  onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))}
                  required
                  autoFocus
                  className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">E-mail</label>
                <input
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  required
                  className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  {editing ? 'Nova senha (deixe vazio para não alterar)' : 'Senha'}
                </label>
                <input
                  type="password"
                  value={form.senha}
                  onChange={(e) => setForm((f) => ({ ...f, senha: e.target.value }))}
                  required={!editing}
                  placeholder={editing ? '••••••••' : ''}
                  className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Perfil</label>
                <select
                  value={form.id_perfil || ''}
                  onChange={(e) => setForm((f) => ({ ...f, id_perfil: Number(e.target.value) }))}
                  required
                  className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                >
                  <option value="">Selecione um perfil</option>
                  {perfis?.map((p) => (
                    <option key={p.id} value={p.id}>{p.nome}</option>
                  ))}
                </select>
              </div>

              {err && (
                <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{err}</p>
              )}

              <div className="flex gap-2 pt-1">
                <Button type="submit" variant="primary" loading={saving} className="flex-1">
                  {saving ? 'Salvando…' : 'Salvar'}
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

      <ConfirmDialog
        open={!!desativando}
        title={`Desativar usuário ${desativando?.nome ?? ''}?`}
        description={
          deactivateErr ||
          'O usuário perde o acesso ao painel, mas continua cadastrado e pode ser reativado depois. O histórico de ações dele é preservado.'
        }
        confirmLabel="Desativar"
        onConfirm={() => desativando && deactivateMut.mutate(desativando.id)}
        onCancel={() => { setDesativando(null); setDeactivateErr('') }}
      />

      <ConfirmDialog
        open={!!excluindo}
        title={`Excluir usuário ${excluindo?.nome ?? ''}?`}
        description={
          deleteErr ||
          'Essa ação remove o usuário permanentemente e não pode ser desfeita. Os registros do log do sistema (histórico de ações) que pertenciam a ele são mantidos, mas deixam de mostrar o autor.'
        }
        confirmLabel="Excluir"
        onConfirm={() => excluindo && deleteMut.mutate(excluindo.id)}
        onCancel={() => { setExcluindo(null); setDeleteErr('') }}
      />
    </div>
  )
}
