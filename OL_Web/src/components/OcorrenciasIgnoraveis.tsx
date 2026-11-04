import { useState } from 'react'
import { fmtDataHora } from '../lib/format'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { EyeOff, Clock3, AlertTriangle } from 'lucide-react'
import { parametrosApi } from '../api/parametros'
import { apiErr } from '../lib/apiError'
import type { Parametro } from '../types'
import Switch from './Switch'
import ConfirmDialog from './ConfirmDialog'

interface Regra {
  /** Chave na tabela `parametro` — a mesma constante lida pelo validador em OL_CORE. */
  chave: string
  /** Ocorrência que deixa de bloquear o pedido quando o parâmetro está ligado. */
  rotulo: string
}

interface Grupo {
  titulo: string
  /** Validador que lê estes parâmetros (referência para quem mantém o código). */
  validador: string
  regras: Regra[]
}

/**
 * Catálogo das ocorrências que podem ser ignoradas. A tela lista SEMPRE estas
 * chaves (e não "tudo que veio de /parametros"): cada uma tem um rótulo de
 * negócio e uma posição fixa, e uma chave que ainda não existe no banco
 * aparece sinalizada em vez de sumir em silêncio.
 *
 * Quando um validador ganhar um novo parâmetro de "ignorar", é só acrescentar
 * a linha aqui — o backend (GET/PUT /parametros) já aceita qualquer chave.
 */
const GRUPOS: Grupo[] = [
  {
    titulo: 'Cliente',
    validador: 'valida_cliente.py',
    regras: [
      { chave: 'CLIENTE_NAO_CADASTRADO', rotulo: 'Cliente não cadastrado' },
      { chave: 'SITUACAO_CLIENTE', rotulo: 'Cliente bloqueado ou inativo' },
      { chave: 'ALVARA_VENCIDO', rotulo: 'Cliente com alvará vencido' },
    ],
  },
  {
    titulo: 'Total do pedido',
    validador: 'valida_pedido.py',
    regras: [
      { chave: 'VALOR_MINIMO_PEDIDO', rotulo: 'Mínimo do pedido não atingido' },
      { chave: 'MINIMO_NAO_CONFIGURADO', rotulo: 'Mínimo não configurado' },
    ],
  },
  {
    titulo: 'Produtos',
    validador: 'valida_produto.py',
    regras: [
      { chave: 'PEDIDO_SEM_ITENS', rotulo: 'Pedido sem itens' },
      { chave: 'PRODUTO_NAO_CADASTRADO', rotulo: 'Produto não cadastrado' },
      { chave: 'PRODUTO_EM_ESTOQUE', rotulo: 'Falta de estoque' },
      { chave: 'PRODUTO_ESTA_NA_CONDICAO', rotulo: 'Produto fora da condição comercial' },
      { chave: 'DESCONTO_MAIOR_QUE_O_CONFIGURADO', rotulo: 'Desconto do item maior que o da condição comercial' },
    ],
  },
  {
    titulo: 'Condição comercial',
    validador: 'valida_condicao.py',
    regras: [
      { chave: 'CONDICAO_CADASTRADA', rotulo: 'Condição não cadastrada' },
      { chave: 'CONDICAO_VALIDA', rotulo: 'Condição vencida' },
      { chave: 'CONDICAO_SEM_DATA_VALIDADE', rotulo: 'Condição sem data de vencimento' },
      { chave: 'VERIFICA_SE_BBS_ESTA_FLAGADO', rotulo: 'Condição com a flag de BBS inativa' },
      { chave: 'VERIFICA_SE_ACESSESIVEL_PARA_OUTRAS_FLAGADO', rotulo: 'Condição com a flag "acessível para outras condições" inativa' },
      { chave: 'VERIFICA_SE_ACESSA_OUTRAS_COND_NA_MAE_ESTA_FLAGADO', rotulo: 'Condição mãe com a flag "acessa outras condições" inativa' },
      { chave: 'IGNORAR_CLIENTE_NAO_CADASTRADO_NA_CONDICAO', rotulo: 'Cliente fora da condição (condição sem a flag "todos os clientes")' },
    ],
  },
]

interface Props {
  parametros: Parametro[] | undefined
  isLoading: boolean
}

export default function OcorrenciasIgnoraveis({ parametros, isLoading }: Props) {
  const qc = useQueryClient()
  const [confirmar, setConfirmar] = useState<Regra | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  const salvar = useMutation({
    mutationFn: ({ chave, valor }: { chave: string; valor: string }) =>
      parametrosApi.update(chave, { valor }),
    onMutate: () => setErro(null),
    onSuccess: (atualizado) => {
      qc.setQueryData<Parametro[]>(['parametros'], (atual) =>
        atual?.map((p) => (p.chave === atualizado.chave ? atualizado : p))
      )
    },
    onError: (e) => setErro(apiErr(e, 'Não foi possível salvar a alteração.')),
  })

  const porChave = new Map((parametros ?? []).map((p) => [p.chave, p]))
  const ausentes = GRUPOS.flatMap((g) => g.regras).filter((r) => !porChave.has(r.chave))
  const totalRegras = GRUPOS.reduce((acc, g) => acc + g.regras.length, 0)
  const totalLigadas = GRUPOS.flatMap((g) => g.regras).filter((r) => porChave.get(r.chave)?.valor === '1').length

  function handleToggle(regra: Regra, ligado: boolean) {
    if (ligado) {
      // Desligar volta ao comportamento padrão (a ocorrência volta a bloquear) —
      // não precisa de confirmação.
      salvar.mutate({ chave: regra.chave, valor: '0' })
    } else {
      // Ligar afrouxa uma validação — confirma antes.
      setConfirmar(regra)
    }
  }

  return (
    <>
      <div className="flex items-end justify-between gap-3 mt-7 mb-2.5 flex-wrap">
        <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">
          Ocorrências ignoradas
        </p>
        {!isLoading && (
          <span className="text-[11px] text-slate-400">
            {totalLigadas} de {totalRegras} sendo ignoradas
          </span>
        )}
      </div>

      <p className="text-sm text-slate-500 leading-relaxed max-w-2xl mb-3">
        Cada validação do pedido gera uma ocorrência quando encontra um problema. Ao{' '}
        <strong>ligar</strong> uma delas, o sistema continua registrando a ocorrência, mas com
        severidade <strong>“Ignorado”</strong> e já marcada como <strong>resolvida</strong> — ela
        deixa de manter o pedido em <strong>“Verificar”</strong>. Vale para as próximas validações
        (pedidos novos ou reprocessados); ocorrências já abertas não mudam sozinhas.
      </p>

      {isLoading ? (
        <div className="bg-white rounded-xl border border-slate-200 p-5 animate-pulse">
          <div className="h-4 bg-slate-100 rounded w-1/3 mb-3" />
          <div className="h-3 bg-slate-100 rounded w-2/3" />
        </div>
      ) : (
        <>
          {ausentes.length > 0 && (
            <div className="mb-3 bg-white rounded-xl border border-amber-200 p-4">
              <div className="flex items-start gap-2.5">
                <AlertTriangle size={16} className="text-amber-500 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-slate-800 text-sm mb-1">
                    {ausentes.length === 1
                      ? '1 parâmetro ainda não cadastrado'
                      : `${ausentes.length} parâmetros ainda não cadastrados`}
                  </p>
                  <p className="text-sm text-slate-500 leading-relaxed max-w-xl">
                    Eles não existem na tabela de parâmetros, então não dá para ligar por aqui — e o
                    validador trata a ausência como desligado:{' '}
                    {ausentes.map((r, i) => (
                      <span key={r.chave}>
                        {i > 0 && ', '}
                        <code className="text-xs bg-slate-100 px-1 py-0.5 rounded">{r.chave}</code>
                      </span>
                    ))}
                    .
                  </p>
                </div>
              </div>
            </div>
          )}

          <div className="space-y-3">
            {GRUPOS.map((grupo) => {
              const ligadasNoGrupo = grupo.regras.filter((r) => porChave.get(r.chave)?.valor === '1').length
              return (
                <div key={grupo.titulo} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div className="px-5 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between gap-3">
                    <p className="font-semibold text-slate-800 text-sm inline-flex items-center gap-1.5">
                      <EyeOff size={14} className="text-slate-400" />
                      {grupo.titulo}
                    </p>
                    <span className="text-[11px] text-slate-400">
                      {ligadasNoGrupo} de {grupo.regras.length} ignoradas
                    </span>
                  </div>

                  <ul className="divide-y divide-slate-100">
                    {grupo.regras.map((regra) => {
                      const param = porChave.get(regra.chave)
                      const ligado = param?.valor === '1'
                      return (
                        <li key={regra.chave} className="px-5 py-3 flex items-center gap-4">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm text-slate-700">{regra.rotulo}</p>
                            <p className="mt-0.5 text-xs text-slate-400 flex items-center gap-1.5 flex-wrap">
                              <code className="font-mono text-[11px]">{regra.chave}</code>
                              {param?.atualizado_em && (
                                <>
                                  <span className="text-slate-300">·</span>
                                  <Clock3 size={11} />
                                  {fmtDataHora(param.atualizado_em)}
                                  {param.atualizado_por ? ` por ${param.atualizado_por}` : ''}
                                </>
                              )}
                            </p>
                          </div>
                          <div className="flex items-center gap-3 shrink-0">
                            <span
                              className={`w-24 text-right text-[11px] font-semibold ${
                                !param ? 'text-amber-600' : ligado ? 'text-green-600' : 'text-slate-400'
                              }`}
                            >
                              {!param ? 'Não cadastrado' : ligado ? 'Ignorando' : 'Bloqueia o pedido'}
                            </span>
                            <Switch
                              checked={ligado}
                              onChange={() => handleToggle(regra, ligado)}
                              disabled={!param || salvar.isPending}
                              label={`Ignorar ocorrência: ${regra.rotulo}`}
                            />
                          </div>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              )
            })}
          </div>

          {erro && (
            <div className="mt-3 px-3 py-2 rounded-lg text-xs border bg-red-50 text-red-700 border-red-200">
              {erro}
            </div>
          )}
        </>
      )}

      <ConfirmDialog
        open={confirmar !== null}
        title={confirmar ? `Ignorar “${confirmar.rotulo}”?` : ''}
        description='A partir de agora, essa ocorrência será registrada como "Ignorado" e já resolvida, e não vai mais manter o pedido em "Verificar". Fica registrado quem alterou e quando.'
        confirmLabel="Ignorar"
        variant="primary"
        onConfirm={() => {
          if (confirmar) salvar.mutate({ chave: confirmar.chave, valor: '1' })
          setConfirmar(null)
        }}
        onCancel={() => setConfirmar(null)}
      />
    </>
  )
}
