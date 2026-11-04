import { useState } from 'react'
import { fmtDataHora } from '../lib/format'
import ErroCarregamento from '../components/ErroCarregamento'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { SlidersHorizontal, ShieldCheck, Clock3, Plus, CheckCircle2, Circle, Send, Save, AlertTriangle, Lock } from 'lucide-react'
import { parametrosApi } from '../api/parametros'
import { apiErr } from '../lib/apiError'
import Switch from '../components/Switch'
import ConfirmDialog from '../components/ConfirmDialog'
import OcorrenciasIgnoraveis from '../components/OcorrenciasIgnoraveis'
import ConfiguracaoDistribuidor from '../components/ConfiguracaoDistribuidor'

const CHAVE_TRANSMISSAO_AUTOMATICA = 'transmissao_automatica_pronto'
const CHAVE_LIMITADOR_ENVIO = 'limitador_de_envio'
const CHAVE_BLOQUEIO_VERIFICAR = 'BLOQUEAR_ENVIO_PEDIDO_VERIFICAR'

// Faixa aceita para o limitador. O teto de 10.000 não é regra de negócio, é
// contenção: reenvio é síncrono (FTP + cópia por arquivo), e um valor absurdo
// aqui só transforma o erro de "lote grande demais" em timeout no meio do
// envio — que é exatamente o que o limitador existe para evitar.
const LIMITE_MIN = 1
const LIMITE_MAX = 10000

export default function Parametrizacao() {
  const qc = useQueryClient()
  const [confirmarLigar, setConfirmarLigar] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const { data: parametros, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['parametros'],
    queryFn: parametrosApi.list,
  })

  const transmissao = parametros?.find((p) => p.chave === CHAVE_TRANSMISSAO_AUTOMATICA)
  const ligado = transmissao?.valor === '1'

  const bloqueio = parametros?.find((p) => p.chave === CHAVE_BLOQUEIO_VERIFICAR)
  const bloqueioLigado = bloqueio?.valor === '1'
  const [confirmarDesligarBloqueio, setConfirmarDesligarBloqueio] = useState(false)
  const [erroBloqueio, setErroBloqueio] = useState<string | null>(null)

  const limitador = parametros?.find((p) => p.chave === CHAVE_LIMITADOR_ENVIO)
  // `null` significa "ainda não editado": o campo mostra o valor do banco e
  // volta a segui-lo sozinho depois de salvar. Espelhar o servidor num estado
  // via useEffect causaria render em cascata (e o lint reprova) — aqui o valor
  // exibido é derivado, não copiado.
  const [limiteDraft, setLimiteDraft] = useState<string | null>(null)
  const [erroLimite, setErroLimite] = useState<string | null>(null)

  const limiteValorBanco = limitador?.valor ?? ''
  const limiteCampo = limiteDraft ?? limiteValorBanco

  const limiteNum = Number(limiteCampo)
  const limiteValido =
    limiteCampo.trim() !== ''
    && Number.isInteger(limiteNum)
    && limiteNum >= LIMITE_MIN
    && limiteNum <= LIMITE_MAX
  const limiteAlterado = limiteCampo.trim() !== limiteValorBanco.trim()

  const salvar = useMutation({
    mutationFn: (valor: string) => parametrosApi.update(CHAVE_TRANSMISSAO_AUTOMATICA, { valor }),
    onMutate: () => setErro(null),
    onSuccess: (atualizado) => {
      qc.setQueryData<typeof parametros>(['parametros'], (atual) =>
        atual?.map((p) => (p.chave === atualizado.chave ? atualizado : p))
      )
    },
    onError: (e) => setErro(apiErr(e, 'Não foi possível salvar a alteração.')),
  })

  const salvarLimite = useMutation({
    mutationFn: (valor: string) => parametrosApi.update(CHAVE_LIMITADOR_ENVIO, { valor }),
    onMutate: () => setErroLimite(null),
    onSuccess: (atualizado) => {
      qc.setQueryData<typeof parametros>(['parametros'], (atual) =>
        atual?.map((p) => (p.chave === atualizado.chave ? atualizado : p))
      )
      setLimiteDraft(null)
    },
    onError: (e) => setErroLimite(apiErr(e, 'Não foi possível salvar o limitador.')),
  })

  function handleSalvarLimite() {
    if (!limiteValido) {
      setErroLimite(`Informe um número inteiro entre ${LIMITE_MIN} e ${LIMITE_MAX}.`)
      return
    }
    salvarLimite.mutate(String(limiteNum))
  }

  const salvarBloqueio = useMutation({
    mutationFn: (valor: string) => parametrosApi.update(CHAVE_BLOQUEIO_VERIFICAR, { valor }),
    onMutate: () => setErroBloqueio(null),
    onSuccess: (atualizado) => {
      qc.setQueryData<typeof parametros>(['parametros'], (atual) =>
        atual?.map((p) => (p.chave === atualizado.chave ? atualizado : p))
      )
    },
    onError: (e) => setErroBloqueio(apiErr(e, 'Não foi possível salvar a alteração.')),
  })

  function handleToggleBloqueio() {
    if (bloqueioLigado) {
      // Desligar LIBERA o envio de pedidos com ocorrência — é o lado arriscado
      // deste parâmetro, então confirma. Ligar volta ao caminho seguro.
      setConfirmarDesligarBloqueio(true)
    } else {
      salvarBloqueio.mutate('1')
    }
  }

  function handleToggle() {
    if (ligado) {
      // Desligar volta ao caminho seguro (revisão manual) — não precisa de
      // confirmação.
      salvar.mutate('0')
    } else {
      // Ligar muda o comportamento automático do sistema — confirma antes.
      setConfirmarLigar(true)
    }
  }

  return (
    <div>
      <div className="mb-1 inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-brand">
        <SlidersHorizontal size={12} />
        Parametrização
      </div>
      <h1 className="text-xl font-semibold text-slate-800 mb-1">Configurações do sistema</h1>
      <p className="text-sm text-slate-500 mb-3 max-w-xl">
        Parâmetros que mudam como o PainelOL se comporta automaticamente — sem precisar alterar
        código ou reiniciar serviço.
      </p>
      <div className="inline-flex items-center gap-1.5 text-xs text-slate-500 bg-white border border-slate-200 rounded-full pl-2 pr-3 py-1.5 mb-6">
        <ShieldCheck size={13} className="text-slate-400" />
        Visível só para <strong className="text-slate-700 font-medium">Administrador</strong> e{' '}
        <strong className="text-slate-700 font-medium">Gerente Comercial</strong>
      </div>

      {/* Sem os parâmetros, os interruptores mostrariam "desligado" por padrão
          — e o usuário poderia ligar algo achando que estava desligado. Na
          falha, a tela não mostra controle nenhum (Q1 da auditoria). */}
      {isError && !parametros ? (
        <ErroCarregamento titulo="Não foi possível carregar os parâmetros." error={error} onRetry={() => refetch()} />
      ) : (<>
      <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400 mb-2.5">
        Distribuidor e ERP
      </p>
      <ConfiguracaoDistribuidor parametros={parametros} isLoading={isLoading} />

      <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400 mt-7 mb-2.5">
        Triagem e transmissão
      </p>

      {isLoading ? (
        <div className="bg-white rounded-xl border border-slate-200 p-5 animate-pulse">
          <div className="h-4 bg-slate-100 rounded w-1/3 mb-3" />
          <div className="h-3 bg-slate-100 rounded w-2/3" />
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-start gap-4">
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-slate-800 text-sm mb-1">
                Transmissão automática de pedidos prontos
              </p>
              <p className="text-sm text-slate-500 leading-relaxed max-w-xl">
                Quando ligado, pedidos que chegam ao status <strong>“Pronto”</strong> na triagem são
                transmitidos direto para a pasta de entrada, sem ação manual. Quando desligado
                (padrão), eles aguardam na fila de triagem até alguém transmitir manualmente.
              </p>
            </div>
            <div className="flex flex-col items-end gap-1.5 shrink-0">
              <Switch
                checked={ligado}
                onChange={handleToggle}
                disabled={salvar.isPending}
                label="Transmissão automática de pedidos prontos"
              />
              <span
                className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                  ligado ? 'text-green-600 bg-green-50' : 'text-slate-400 bg-slate-100'
                }`}
              >
                {ligado ? <CheckCircle2 size={10} /> : <Circle size={10} />}
                {ligado ? 'Ligado' : 'Desligado'}
              </span>
            </div>
          </div>

          {erro && (
            <div className="mt-3 px-3 py-2 rounded-lg text-xs border bg-red-50 text-red-700 border-red-200">
              {erro}
            </div>
          )}

          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center gap-1.5 text-xs text-slate-400">
            <Clock3 size={12} />
            {transmissao?.atualizado_em
              ? `Última alteração: ${fmtDataHora(transmissao.atualizado_em)}${
                  transmissao.atualizado_por ? ` por ${transmissao.atualizado_por}` : ''
                }`
              : 'Nunca alterado'}
          </div>
        </div>
      )}

      {!isLoading && (
        !bloqueio ? (
          /* Parâmetro lido do banco: enquanto a linha não existir, o backend não
             bloqueia nada e o PUT devolveria 404 — a tela avisa em vez de oferecer
             um switch que não salva. */
          <div className="mt-3 bg-white rounded-xl border border-amber-200 p-5">
            <div className="flex items-start gap-2.5">
              <AlertTriangle size={16} className="text-amber-500 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-slate-800 text-sm mb-1">
                  Bloqueio de envio de pedidos em Verificar ainda não cadastrado
                </p>
                <p className="text-sm text-slate-500 leading-relaxed max-w-xl">
                  O parâmetro <code className="text-xs bg-slate-100 px-1 py-0.5 rounded">{CHAVE_BLOQUEIO_VERIFICAR}</code>{' '}
                  não existe na tabela de parâmetros. Enquanto isso, o envio manual não é restringido
                  por status.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="mt-3 bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-start gap-4">
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-slate-800 text-sm mb-1 inline-flex items-center gap-1.5">
                  <Lock size={14} className="text-slate-400" />
                  Bloquear envio de pedidos em Verificar
                </p>
                <p className="text-sm text-slate-500 leading-relaxed max-w-xl">
                  Quando ligado, só pedidos com status <strong>“Pronto”</strong> podem ser transmitidos
                  manualmente (individual ou em lote). Pedidos em <strong>“Verificar”</strong> ficam
                  barrados até a ocorrência ser resolvida e o pedido reprocessado. Quando desligado,
                  eles podem ser transmitidos mesmo com ocorrência aberta. Não muda a transmissão
                  automática.
                </p>
              </div>
              <div className="flex flex-col items-end gap-1.5 shrink-0">
                <Switch
                  checked={bloqueioLigado}
                  onChange={handleToggleBloqueio}
                  disabled={salvarBloqueio.isPending}
                  label="Bloquear envio de pedidos em Verificar"
                />
                <span
                  className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                    bloqueioLigado ? 'text-green-600 bg-green-50' : 'text-slate-400 bg-slate-100'
                  }`}
                >
                  {bloqueioLigado ? <CheckCircle2 size={10} /> : <Circle size={10} />}
                  {bloqueioLigado ? 'Ligado' : 'Desligado'}
                </span>
              </div>
            </div>

            {erroBloqueio && (
              <div className="mt-3 px-3 py-2 rounded-lg text-xs border bg-red-50 text-red-700 border-red-200">
                {erroBloqueio}
              </div>
            )}

            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center gap-1.5 text-xs text-slate-400">
              <Clock3 size={12} />
              {bloqueio.atualizado_em
                ? `Última alteração: ${fmtDataHora(bloqueio.atualizado_em)}${
                    bloqueio.atualizado_por ? ` por ${bloqueio.atualizado_por}` : ''
                  }`
                : 'Nunca alterado'}
            </div>
          </div>
        )
      )}

      <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400 mt-7 mb-2.5">
        Envio de arquivos
      </p>

      {isLoading ? (
        <div className="bg-white rounded-xl border border-slate-200 p-5 animate-pulse">
          <div className="h-4 bg-slate-100 rounded w-1/3 mb-3" />
          <div className="h-3 bg-slate-100 rounded w-2/3" />
        </div>
      ) : !limitador ? (
        /* O parâmetro é lido do banco; enquanto a linha não existir, o backend
           cai no padrão (250) e o PUT devolveria 404 — então a tela avisa em
           vez de oferecer um campo que não salva. */
        <div className="bg-white rounded-xl border border-amber-200 p-5">
          <div className="flex items-start gap-2.5">
            <AlertTriangle size={16} className="text-amber-500 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-slate-800 text-sm mb-1">
                Limitador de envio ainda não cadastrado
              </p>
              <p className="text-sm text-slate-500 leading-relaxed max-w-xl">
                O parametro <code className="text-xs bg-slate-100 px-1 py-0.5 rounded">limitador_de_envio</code>{' '}
                não existe na tabela de parâmetros. Enquanto isso, o reenvio por período usa o
                padrão de <strong>250</strong> pedidos por disparo.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-start gap-4 flex-wrap">
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-slate-800 text-sm mb-1">
                Limitador de envio de arquivos
              </p>
              <p className="text-sm text-slate-500 leading-relaxed max-w-xl">
                Quantidade máxima de pedidos que um reenvio por período pode disparar de uma vez
                (tela de <strong>Histórico</strong>). Acima disso o sistema recusa o disparo e pede
                para estreitar o período — o envio é síncrono, então um lote grande demais morreria
                no meio.
              </p>
            </div>
            <div className="flex items-end gap-2 shrink-0">
              <div>
                <label htmlFor="limitador" className="block text-xs font-medium text-slate-600 mb-1">
                  Pedidos por envio
                </label>
                <input
                  id="limitador"
                  type="number"
                  min={LIMITE_MIN}
                  max={LIMITE_MAX}
                  step={1}
                  value={limiteCampo}
                  onChange={(e) => { setLimiteDraft(e.target.value); setErroLimite(null) }}
                  disabled={salvarLimite.isPending}
                  className="w-32 px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                />
              </div>
              <button
                onClick={handleSalvarLimite}
                disabled={salvarLimite.isPending || !limiteAlterado || !limiteValido}
                className="flex items-center gap-1.5 px-4 py-2 bg-brand text-white text-sm font-medium rounded-lg transition-colors hover:bg-brand-dark disabled:opacity-50"
              >
                <Save size={14} />
                {salvarLimite.isPending ? 'Salvando…' : 'Salvar'}
              </button>
            </div>
          </div>

          {erroLimite && (
            <div className="mt-3 px-3 py-2 rounded-lg text-xs border bg-red-50 text-red-700 border-red-200">
              {erroLimite}
            </div>
          )}

          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center gap-1.5 text-xs text-slate-400 flex-wrap">
            <Send size={12} />
            <span>Vale para o reenvio por período do Histórico.</span>
            <span className="text-slate-300">·</span>
            <Clock3 size={12} />
            {limitador.atualizado_em
              ? `Última alteração: ${fmtDataHora(limitador.atualizado_em)}${
                  limitador.atualizado_por ? ` por ${limitador.atualizado_por}` : ''
                }`
              : 'Nunca alterado'}
          </div>
        </div>
      )}

      <OcorrenciasIgnoraveis parametros={parametros} isLoading={isLoading} />
      </>)}

      <div className="mt-7 border border-dashed border-slate-300 rounded-xl px-5 py-3.5 flex items-center gap-2.5 text-xs text-slate-400">
        <Plus size={14} />
        Novos parâmetros aparecerão aqui conforme forem definidos
      </div>

      <ConfirmDialog
        open={confirmarLigar}
        title="Ativar transmissão automática?"
        description='A partir de agora, todo pedido que chegar ao status "Pronto" será transmitido para a pasta de entrada automaticamente, sem revisão manual antes do envio. Essa mudança fica registrada no histórico de configurações.'
        confirmLabel="Ativar"
        variant="primary"
        onConfirm={() => {
          setConfirmarLigar(false)
          salvar.mutate('1')
        }}
        onCancel={() => setConfirmarLigar(false)}
      />

      <ConfirmDialog
        open={confirmarDesligarBloqueio}
        title="Liberar envio de pedidos em Verificar?"
        description='A partir de agora, operadores poderão transmitir pedidos em "Verificar", mesmo com ocorrência aberta. Fica registrado quem alterou e quando.'
        confirmLabel="Liberar envio"
        variant="primary"
        onConfirm={() => {
          setConfirmarDesligarBloqueio(false)
          salvarBloqueio.mutate('0')
        }}
        onCancel={() => setConfirmarDesligarBloqueio(false)}
      />
    </div>
  )
}
