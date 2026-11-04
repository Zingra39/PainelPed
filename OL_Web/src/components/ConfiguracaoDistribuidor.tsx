import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Building2, Clock3, Save, Warehouse } from 'lucide-react'
import { CHAVE_QUERY_PENDENCIAS, parametrosApi } from '../api/parametros'
import { apiErr } from '../lib/apiError'
import { fmtDataHora } from '../lib/format'
import type { Parametro } from '../types'

const CHAVE_CNPJ = 'cnpj_distribuidor'
const CHAVE_FILIAIS = 'filiais_estoque'

const soDigitos = (v: string) => v.replace(/\D/g, '')

/** 11222333000181 -> 11.222.333/0001-81 (parcial enquanto digita). */
function mascaraCnpj(v: string): string {
  const d = soDigitos(v).slice(0, 14)
  return d
    .replace(/^(\d{2})(\d)/, '$1.$2')
    .replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3')
    .replace(/\.(\d{3})(\d)/, '.$1/$2')
    .replace(/(\d{4})(\d)/, '$1-$2')
}

/** "12328; 12329 12328" -> ["12328", "12329"] — só para pré-visualizar; a API valida. */
function listarFiliais(v: string): string[] {
  return [...new Set(v.split(/[,;\s]+/).map((p) => p.trim()).filter(Boolean))]
}

function UltimaAlteracao({ p }: { p: Parametro }) {
  return (
    <div className="mt-4 pt-3 border-t border-slate-100 flex items-center gap-1.5 text-xs text-slate-400">
      <Clock3 size={12} />
      {p.atualizado_em
        ? `Última alteração: ${fmtDataHora(p.atualizado_em)}${p.atualizado_por ? ` por ${p.atualizado_por}` : ''}`
        : 'Nunca alterado'}
    </div>
  )
}

function NaoCadastrado({ chave, titulo }: { chave: string; titulo: string }) {
  return (
    <div className="mt-3 bg-white rounded-xl border border-amber-200 p-5 flex items-start gap-2.5">
      <AlertTriangle size={16} className="text-amber-500 shrink-0 mt-0.5" />
      <div>
        <p className="font-semibold text-slate-800 text-sm mb-1">{titulo} ainda não cadastrado</p>
        <p className="text-sm text-slate-500">
          O parâmetro <code className="text-xs bg-slate-100 px-1 py-0.5 rounded">{chave}</code> não existe na
          tabela de parâmetros. Ele é criado na próxima subida da API.
        </p>
      </div>
    </div>
  )
}

/** Hook de um campo texto ligado a um parâmetro: rascunho local + salvar. */
function useCampoParametro(chave: string, parametro: Parametro | undefined) {
  const qc = useQueryClient()
  // null = não editado: o campo segue o valor do banco (mesmo padrão do limitador).
  const [rascunho, setRascunho] = useState<string | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const valorBanco = parametro?.valor ?? ''

  const salvar = useMutation({
    mutationFn: (valor: string) => parametrosApi.update(chave, { valor }),
    onMutate: () => setErro(null),
    onSuccess: (atualizado) => {
      qc.setQueryData<Parametro[]>(['parametros'], (atual) =>
        atual?.map((p) => (p.chave === atualizado.chave ? atualizado : p)),
      )
      qc.invalidateQueries({ queryKey: CHAVE_QUERY_PENDENCIAS })
      setRascunho(null)
    },
    onError: (e) => setErro(apiErr(e, 'Não foi possível salvar.')),
  })

  return {
    valorBanco,
    campo: rascunho ?? valorBanco,
    alterado: rascunho !== null && rascunho.trim() !== valorBanco.trim(),
    editar: (v: string) => { setRascunho(v); setErro(null) },
    erro, setErro, salvar,
  }
}

interface Props {
  parametros: Parametro[] | undefined
  isLoading: boolean
}

/**
 * Seção "Distribuidor e ERP" da Parametrização: dados que antes ficavam fixos
 * no código (I10 da auditoria) — CNPJ do distribuidor gravado nos arquivos e
 * as filiais do ERP cujo estoque é considerado.
 */
export default function ConfiguracaoDistribuidor({ parametros, isLoading }: Props) {
  const cnpjParam = parametros?.find((p) => p.chave === CHAVE_CNPJ)
  const filiaisParam = parametros?.find((p) => p.chave === CHAVE_FILIAIS)

  const cnpj = useCampoParametro(CHAVE_CNPJ, cnpjParam)
  const filiais = useCampoParametro(CHAVE_FILIAIS, filiaisParam)

  const cnpjDigitos = soDigitos(cnpj.campo)
  const cnpjConfigurado = soDigitos(cnpj.valorBanco).length > 0
  const filiaisLista = listarFiliais(filiais.campo)

  function salvarCnpj() {
    if (cnpjDigitos.length !== 14) {
      cnpj.setErro('Informe os 14 dígitos do CNPJ.')
      return
    }
    cnpj.salvar.mutate(cnpjDigitos)
  }

  function salvarFiliais() {
    const invalida = filiaisLista.find((f) => !/^\d+$/.test(f) || Number(f) <= 0)
    if (invalida) {
      filiais.setErro(`Código de filial inválido: "${invalida}". Use números separados por vírgula.`)
      return
    }
    filiais.salvar.mutate(filiaisLista.join(','))
  }

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-5 animate-pulse">
        <div className="h-4 bg-slate-100 rounded w-1/3 mb-3" />
        <div className="h-3 bg-slate-100 rounded w-2/3" />
      </div>
    )
  }

  const inputCls =
    'px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50'
  const botaoCls =
    'flex items-center gap-1.5 px-4 py-2 bg-brand text-white text-sm font-medium rounded-lg transition-colors hover:bg-brand-dark disabled:opacity-50'

  return (
    <>
      {/* CNPJ do distribuidor */}
      {!cnpjParam ? (
        <NaoCadastrado chave={CHAVE_CNPJ} titulo="CNPJ do distribuidor" />
      ) : (
        <div className={`bg-white rounded-xl border p-5 ${cnpjConfigurado ? 'border-slate-200' : 'border-amber-300'}`}>
          <div className="flex items-start gap-4 flex-wrap">
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-slate-800 text-sm mb-1 inline-flex items-center gap-1.5">
                <Building2 size={14} className="text-slate-400" />
                CNPJ do distribuidor
              </p>
              <p className="text-sm text-slate-500 leading-relaxed max-w-xl">
                Gravado nos arquivos de <strong>retorno</strong>, <strong>espelho</strong>,{' '}
                <strong>cancelamento</strong> e <strong>estoque</strong> enviados à indústria.
              </p>
            </div>
            <div className="flex items-end gap-2 shrink-0">
              <div>
                <label htmlFor="cnpj-distribuidor" className="block text-xs font-medium text-slate-600 mb-1">
                  CNPJ
                </label>
                <input
                  id="cnpj-distribuidor"
                  inputMode="numeric"
                  placeholder="00.000.000/0000-00"
                  value={mascaraCnpj(cnpj.campo)}
                  onChange={(e) => cnpj.editar(soDigitos(e.target.value))}
                  disabled={cnpj.salvar.isPending}
                  className={`w-48 ${inputCls}`}
                />
              </div>
              <button
                onClick={salvarCnpj}
                disabled={cnpj.salvar.isPending || !cnpj.alterado}
                className={botaoCls}
              >
                <Save size={14} />
                {cnpj.salvar.isPending ? 'Salvando…' : 'Salvar'}
              </button>
            </div>
          </div>

          {!cnpjConfigurado && (
            <div className="mt-3 flex items-start gap-2 px-3 py-2 rounded-lg text-xs border bg-amber-50 text-amber-800 border-amber-200">
              <AlertTriangle size={14} className="shrink-0 mt-px text-amber-500" />
              <span>
                CNPJ não configurado: os serviços <strong>não geram</strong> retorno, espelho, cancelamento nem
                estoque até ele ser informado.
              </span>
            </div>
          )}
          {cnpj.erro && (
            <div className="mt-3 px-3 py-2 rounded-lg text-xs border bg-red-50 text-red-700 border-red-200">
              {cnpj.erro}
            </div>
          )}
          <UltimaAlteracao p={cnpjParam} />
        </div>
      )}

      {/* Filiais de estoque */}
      {!filiaisParam ? (
        <NaoCadastrado chave={CHAVE_FILIAIS} titulo="Filiais de estoque" />
      ) : (
        <div className="mt-3 bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-start gap-4 flex-wrap">
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-slate-800 text-sm mb-1 inline-flex items-center gap-1.5">
                <Warehouse size={14} className="text-slate-400" />
                Filiais de estoque
              </p>
              <p className="text-sm text-slate-500 leading-relaxed max-w-xl">
                Códigos das filiais do ERP cujo estoque o sistema considera — na validação de falta de
                estoque, na quantidade atendida e no arquivo de estoque. Com várias filiais, o estoque é a{' '}
                <strong>soma</strong> delas. <strong>Vazio</strong>: não filtra por filial (soma todas).
              </p>
            </div>
            <div className="flex items-end gap-2 shrink-0">
              <div>
                <label htmlFor="filiais-estoque" className="block text-xs font-medium text-slate-600 mb-1">
                  Códigos (separados por vírgula)
                </label>
                <input
                  id="filiais-estoque"
                  placeholder="ex.: 12328, 12329"
                  value={filiais.campo}
                  onChange={(e) => filiais.editar(e.target.value)}
                  disabled={filiais.salvar.isPending}
                  className={`w-56 ${inputCls}`}
                />
              </div>
              <button
                onClick={salvarFiliais}
                disabled={filiais.salvar.isPending || !filiais.alterado}
                className={botaoCls}
              >
                <Save size={14} />
                {filiais.salvar.isPending ? 'Salvando…' : 'Salvar'}
              </button>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs">
            {filiaisLista.length ? (
              filiaisLista.map((f) => (
                <span key={f} className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium">
                  Filial {f}
                </span>
              ))
            ) : (
              <span className="text-slate-400">Nenhuma filial: o estoque considera todas as filiais.</span>
            )}
          </div>
          {filiais.erro && (
            <div className="mt-3 px-3 py-2 rounded-lg text-xs border bg-red-50 text-red-700 border-red-200">
              {filiais.erro}
            </div>
          )}
          <UltimaAlteracao p={filiaisParam} />
        </div>
      )}
    </>
  )
}
