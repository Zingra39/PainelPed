import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { industriasApi, type IndustriaUpdate } from '../../api/industrias'
import ConfirmDialog from '../../components/ConfirmDialog'
import FlashBanner from '../../components/FlashBanner'
import { Button, IconButton } from '../../components/Button'
import { useFlash } from '../../hooks/useFlash'
import { fmtDataHora } from '../../lib/format'
import {
  ArrowLeft, Building2, FolderTree, Server, ChevronDown, ChevronUp,
  Power, Trash2, Truck, Plus, X, AlertTriangle,
} from 'lucide-react'
import type { IndustriaFornecedor, IndustriaFtp } from '../../types'
import { apiErr } from '../../lib/apiError'


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
      {open && <div className="border-t border-slate-100 px-5 py-4">{children}</div>}
    </div>
  )
}

interface FieldProps {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
}
function Field({ label, value, onChange, placeholder }: FieldProps) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-700 mb-1">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </div>
  )
}

function SaveButton({ pending, onClick }: { pending: boolean; onClick: () => void }) {
  return (
    <Button variant="primary" onClick={onClick} loading={pending} className="mt-4">
      {pending ? 'Salvando…' : 'Salvar'}
    </Button>
  )
}

const EMPTY_FTP: IndustriaFtp = {
  ftp_pedidos: '', ftp_retornos: '', ftp_espelhos: '', ftp_cancelados: '', ftp_estoques: '',
}

/** Linha editável da seção "Fornecedores no ERP" (o código fica em texto enquanto digita). */
interface LinhaFornecedor {
  cod: string
  descricao: string
}

const paraLinhas = (lista: IndustriaFornecedor[] | undefined): LinhaFornecedor[] =>
  (lista ?? []).map((f) => ({ cod: String(f.cod_fornecedor), descricao: f.descricao ?? '' }))

/** Converte as linhas para o payload da API, ou devolve a mensagem do problema. */
function validarFornecedores(linhas: LinhaFornecedor[]): IndustriaFornecedor[] | string {
  const preenchidas = linhas.filter((l) => l.cod.trim() || l.descricao.trim())
  const vistos = new Set<number>()
  const itens: IndustriaFornecedor[] = []
  for (const l of preenchidas) {
    const cod = l.cod.trim()
    if (!/^\d+$/.test(cod) || Number(cod) <= 0) {
      return `Código de fornecedor inválido: "${cod || '(vazio)'}". Use só números.`
    }
    if (vistos.has(Number(cod))) return `Código de fornecedor repetido: ${cod}.`
    vistos.add(Number(cod))
    itens.push({ cod_fornecedor: Number(cod), descricao: l.descricao.trim() || null })
  }
  return itens
}

export default function IndustriaDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const flash = useFlash(5000)
  const [showConfirmDelete, setShowConfirmDelete] = useState(false)
  const [ftpEditing, setFtpEditing] = useState(false)

  const { data: industria, isLoading, isError, error } = useQuery({
    queryKey: ['industria-detalhes', id],
    queryFn: () => industriasApi.get(Number(id)),
    enabled: !!id,
  })

  const [geral, setGeral] = useState({ nome: '', cnpj: '', layout: '', id_bbs: '', cond_mae: '' })
  const [pastasDispFarm, setPastasDispFarm] = useState({
    pasta_envio: '', pasta_retorno_envio: '', pasta_retorno_espelho: '', pasta_envio_cancelamento: '',
  })
  const [pastasErp, setPastasErp] = useState({
    pasta_pedido_original: '', pasta_entrada: '', pasta_retorno: '', pasta_espelho: '',
    pasta_backup_pedido: '', pasta_cancelamento: '', pasta_estoque: '',
  })
  const [ftp, setFtp] = useState<IndustriaFtp>(EMPTY_FTP)
  const [fornecedores, setFornecedores] = useState<LinhaFornecedor[]>([])
  const [erroFornecedores, setErroFornecedores] = useState<string | null>(null)

  useEffect(() => {
    if (!industria) return
    setGeral({
      nome: industria.nome ?? '',
      cnpj: industria.cnpj ?? '',
      layout: industria.layout ?? '',
      id_bbs: industria.id_bbs != null ? String(industria.id_bbs) : '',
      cond_mae: industria.cond_mae != null ? String(industria.cond_mae) : '',
    })
    setPastasDispFarm({
      pasta_envio: industria.pasta_envio ?? '',
      pasta_retorno_envio: industria.pasta_retorno_envio ?? '',
      pasta_retorno_espelho: industria.pasta_retorno_espelho ?? '',
      pasta_envio_cancelamento: industria.pasta_envio_cancelamento ?? '',
    })
    setPastasErp({
      pasta_pedido_original: industria.pasta_pedido_original ?? '',
      pasta_entrada: industria.pasta_entrada ?? '',
      pasta_retorno: industria.pasta_retorno ?? '',
      pasta_espelho: industria.pasta_espelho ?? '',
      pasta_backup_pedido: industria.pasta_backup_pedido ?? '',
      pasta_cancelamento: industria.pasta_cancelamento ?? '',
      pasta_estoque: industria.pasta_estoque ?? '',
    })
    setFtp(industria.ftp ?? EMPTY_FTP)
    setFtpEditing(false)
    setFornecedores(paraLinhas(industria.fornecedores))
    setErroFornecedores(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [industria?.id])

  const showMsg = (ok: boolean, text: string) => flash.mostrar(ok ? 'sucesso' : 'erro', text)

  function invalidate() {
    qc.invalidateQueries({ queryKey: ['industria-detalhes', id] })
    qc.invalidateQueries({ queryKey: ['industrias'] })
  }

  const updateMut = useMutation({
    mutationFn: (payload: IndustriaUpdate) => industriasApi.update(Number(id), payload),
    onSuccess: () => { invalidate(); showMsg(true, 'Alterações salvas com sucesso.') },
    onError: (e: unknown) => showMsg(false, apiErr(e, 'Erro ao salvar alterações.')),
  })

  const deleteMut = useMutation({
    mutationFn: () => industriasApi.remove(Number(id)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['industrias'] })
      navigate('/industrias')
    },
    onError: (e: unknown) => { setShowConfirmDelete(false); showMsg(false, apiErr(e, 'Erro ao excluir indústria.')) },
  })

  function salvarGeral() {
    updateMut.mutate({
      nome: geral.nome,
      cnpj: geral.cnpj || undefined,
      layout: geral.layout || undefined,
      id_bbs: geral.id_bbs ? Number(geral.id_bbs) : undefined,
      cond_mae: geral.cond_mae ? Number(geral.cond_mae) : undefined,
    })
  }
  function salvarPastasDispFarm() {
    updateMut.mutate(pastasDispFarm)
  }
  function salvarPastasErp() {
    updateMut.mutate(pastasErp)
  }
  function salvarFtp() {
    updateMut.mutate({ ftp })
  }
  function salvarFornecedores() {
    const resultado = validarFornecedores(fornecedores)
    if (typeof resultado === 'string') {
      setErroFornecedores(resultado)
      return
    }
    setErroFornecedores(null)
    updateMut.mutate(
      { fornecedores: resultado },
      // O useEffect só ressincroniza ao trocar de indústria: aqui alinha a
      // tela com o que foi gravado (linhas vazias somem, ordem por código).
      { onSuccess: (salva) => setFornecedores(paraLinhas(salva.fornecedores)) },
    )
  }
  function editarFornecedor(i: number, campo: keyof LinhaFornecedor, valor: string) {
    setFornecedores((lista) => lista.map((l, idx) => (idx === i ? { ...l, [campo]: valor } : l)))
    setErroFornecedores(null)
  }
  function toggleAtivo() {
    if (!industria) return
    updateMut.mutate({ ativo: !industria.ativo })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (isError) {
    const errMsg = apiErr(error, 'Não foi possível carregar a indústria.')
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <p className="text-red-600 font-medium">{errMsg}</p>
        <button onClick={() => navigate('/industrias')} className="text-sm text-slate-500 hover:text-slate-700 underline">
          Voltar para a lista
        </button>
      </div>
    )
  }

  if (!industria) return null

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div className="flex items-start gap-3">
          <IconButton label="Voltar para a lista" appearance="outline" onClick={() => navigate('/industrias')} className="mt-0.5">
            <ArrowLeft size={15} />
          </IconButton>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-slate-800">{industria.nome}</h1>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                industria.ativo ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
              }`}>
                {industria.ativo ? 'Ativa' : 'Inativa'}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Criada em {fmtDataHora(industria.criado_em)} · Atualizada em {fmtDataHora(industria.atualizado_em)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleAtivo}
            disabled={updateMut.isPending}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-600 text-sm font-medium transition-colors disabled:opacity-60"
          >
            <Power size={14} />
            {industria.ativo ? 'Desativar' : 'Ativar'}
          </button>
          <button
            onClick={() => setShowConfirmDelete(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-red-200 bg-white hover:bg-red-50 text-red-500 text-sm font-medium transition-colors"
          >
            <Trash2 size={14} />
            Excluir
          </button>
        </div>
      </div>

      <FlashBanner flash={flash.flash} />

      {/* Dados gerais */}
      <Section title="Dados gerais" icon={<Building2 size={15} className="text-slate-400" />}>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Nome" value={geral.nome} onChange={(v) => setGeral((f) => ({ ...f, nome: v }))} />
          <Field label="CNPJ" value={geral.cnpj} onChange={(v) => setGeral((f) => ({ ...f, cnpj: v }))} />
          <Field label="Layout" value={geral.layout} onChange={(v) => setGeral((f) => ({ ...f, layout: v }))} placeholder="ex.: closeup" />
          <Field label="ID BBS" value={geral.id_bbs} onChange={(v) => setGeral((f) => ({ ...f, id_bbs: v }))} />
          <Field label="Condição Mãe" value={geral.cond_mae} onChange={(v) => setGeral((f) => ({ ...f, cond_mae: v }))} />
        </div>
        <SaveButton pending={updateMut.isPending} onClick={salvarGeral} />
      </Section>

      {/* Pastas DispFarm */}
      <Section title="Pastas DispFarm" icon={<FolderTree size={15} className="text-slate-400" />}>
        <div className="grid grid-cols-1 gap-4">
          <Field label="Pasta de envio" value={pastasDispFarm.pasta_envio}
            onChange={(v) => setPastasDispFarm((f) => ({ ...f, pasta_envio: v }))} />
          <Field label="Pasta de envio — retorno" value={pastasDispFarm.pasta_retorno_envio}
            onChange={(v) => setPastasDispFarm((f) => ({ ...f, pasta_retorno_envio: v }))} />
          <Field label="Pasta de envio — NF/espelho" value={pastasDispFarm.pasta_retorno_espelho}
            onChange={(v) => setPastasDispFarm((f) => ({ ...f, pasta_retorno_espelho: v }))} />
          <Field label="Pasta de envio — cancelamento" value={pastasDispFarm.pasta_envio_cancelamento}
            onChange={(v) => setPastasDispFarm((f) => ({ ...f, pasta_envio_cancelamento: v }))} />
        </div>
        <SaveButton pending={updateMut.isPending} onClick={salvarPastasDispFarm} />
      </Section>

      {/* Pastas ERP */}
      <Section title="Pastas ERP" icon={<FolderTree size={15} className="text-slate-400" />}>
        <div className="grid grid-cols-1 gap-4">
          <Field label="Pedido original" value={pastasErp.pasta_pedido_original}
            onChange={(v) => setPastasErp((f) => ({ ...f, pasta_pedido_original: v }))} />
          <Field label="Entrada" value={pastasErp.pasta_entrada}
            onChange={(v) => setPastasErp((f) => ({ ...f, pasta_entrada: v }))} />
          <Field label="Retorno" value={pastasErp.pasta_retorno}
            onChange={(v) => setPastasErp((f) => ({ ...f, pasta_retorno: v }))} />
          <Field label="NF/espelho" value={pastasErp.pasta_espelho}
            onChange={(v) => setPastasErp((f) => ({ ...f, pasta_espelho: v }))} />
          <Field label="Backup" value={pastasErp.pasta_backup_pedido}
            onChange={(v) => setPastasErp((f) => ({ ...f, pasta_backup_pedido: v }))} />
          <Field label="Cancelamento" value={pastasErp.pasta_cancelamento}
            onChange={(v) => setPastasErp((f) => ({ ...f, pasta_cancelamento: v }))} />
          <Field label="Estoque" value={pastasErp.pasta_estoque}
            onChange={(v) => setPastasErp((f) => ({ ...f, pasta_estoque: v }))} />
        </div>
        <SaveButton pending={updateMut.isPending} onClick={salvarPastasErp} />
      </Section>

      {/* Fornecedores no ERP */}
      <Section title="Fornecedores no ERP" icon={<Truck size={15} className="text-slate-400" />}>
        <p className="text-sm text-slate-500 mb-3 max-w-2xl">
          Códigos com que esta indústria está cadastrada como <strong>fornecedor no ERP</strong>. Definem quais
          produtos entram no arquivo de estoque enviado a ela.
        </p>

        {industria.fornecedores.length === 0 && (
          <div className="mb-3 flex items-start gap-2 px-3 py-2 rounded-lg text-xs border bg-amber-50 text-amber-800 border-amber-200">
            <AlertTriangle size={14} className="shrink-0 mt-px text-amber-500" />
            <span>
              Nenhum código cadastrado: o arquivo de estoque desta indústria <strong>não é gerado</strong>.
            </span>
          </div>
        )}

        {fornecedores.length > 0 && (
          <div className="space-y-2">
            <div className="grid grid-cols-[10rem_1fr_2.25rem] gap-2 text-xs font-medium text-slate-600">
              <span>Código no ERP</span>
              <span>Descrição (opcional)</span>
              <span />
            </div>
            {fornecedores.map((linha, i) => (
              <div key={i} className="grid grid-cols-[10rem_1fr_2.25rem] gap-2 items-center">
                <input
                  inputMode="numeric"
                  aria-label={`Código do fornecedor ${i + 1}`}
                  value={linha.cod}
                  onChange={(e) => editarFornecedor(i, 'cod', e.target.value.replace(/\D/g, ''))}
                  placeholder="ex.: 10423"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <input
                  aria-label={`Descrição do fornecedor ${i + 1}`}
                  value={linha.descricao}
                  maxLength={100}
                  onChange={(e) => editarFornecedor(i, 'descricao', e.target.value)}
                  placeholder="ex.: Hypera — linha farma"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <IconButton
                  label={`Remover fornecedor ${linha.cod || i + 1}`}
                  appearance="outline"
                  onClick={() => setFornecedores((lista) => lista.filter((_, idx) => idx !== i))}
                >
                  <X size={14} />
                </IconButton>
              </div>
            ))}
          </div>
        )}

        <button
          onClick={() => setFornecedores((lista) => [...lista, { cod: '', descricao: '' }])}
          className="mt-3 inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-dashed border-slate-300 text-slate-600 text-sm hover:bg-slate-50 transition-colors"
        >
          <Plus size={14} />
          Adicionar código
        </button>

        {erroFornecedores && (
          <div className="mt-3 px-3 py-2 rounded-lg text-xs border bg-red-50 text-red-700 border-red-200">
            {erroFornecedores}
          </div>
        )}
        <div>
          <SaveButton pending={updateMut.isPending} onClick={salvarFornecedores} />
        </div>
      </Section>

      {/* FTP */}
      <Section title="FTP" icon={<Server size={15} className="text-slate-400" />}>
        {!industria.ftp && !ftpEditing ? (
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-400">FTP não configurado para esta indústria.</p>
            <button
              onClick={() => setFtpEditing(true)}
              className="px-3 py-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-600 text-sm font-medium transition-colors"
            >
              Configurar FTP
            </button>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4">
              <Field label="Caminho de pedidos" value={ftp.ftp_pedidos ?? ''}
                onChange={(v) => setFtp((f) => ({ ...f, ftp_pedidos: v }))} />
              <Field label="Caminho de retornos" value={ftp.ftp_retornos ?? ''}
                onChange={(v) => setFtp((f) => ({ ...f, ftp_retornos: v }))} />
              <Field label="Caminho de espelhos" value={ftp.ftp_espelhos ?? ''}
                onChange={(v) => setFtp((f) => ({ ...f, ftp_espelhos: v }))} />
              <Field label="Caminho de cancelados" value={ftp.ftp_cancelados ?? ''}
                onChange={(v) => setFtp((f) => ({ ...f, ftp_cancelados: v }))} />
              <Field label="Caminho de estoques" value={ftp.ftp_estoques ?? ''}
                onChange={(v) => setFtp((f) => ({ ...f, ftp_estoques: v }))} />
            </div>
            <p className="text-xs text-slate-400 mt-3">
              Host, usuário e senha do FTP são globais para todo o sistema — aqui só os caminhos por indústria.
            </p>
            <SaveButton pending={updateMut.isPending} onClick={salvarFtp} />
          </>
        )}
      </Section>

      <ConfirmDialog
        open={showConfirmDelete}
        title={`Excluir ${industria.nome}?`}
        description="Essa ação remove definitivamente a indústria. Não é possível excluir se houver pedidos vinculados a ela."
        confirmLabel="Excluir"
        onConfirm={() => deleteMut.mutate()}
        onCancel={() => setShowConfirmDelete(false)}
      />
    </div>
  )
}
