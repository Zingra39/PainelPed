import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { servicosApi } from '../api/servicos'
import { RefreshCw, CheckCircle, XCircle, Clock, Play, Loader2 } from 'lucide-react'
import { IconButton } from '../components/Button'
import FlashBanner from '../components/FlashBanner'
import ErroCarregamento from '../components/ErroCarregamento'
import { useFlash } from '../hooks/useFlash'
import { apiErr } from '../lib/apiError'
import { fmtDataHora } from '../lib/format'

export default function Servicos() {
  const qc = useQueryClient()
  // A mensagem aparece no card do serviço executado (chave = nome do serviço).
  const flash = useFlash(3000)

  const { data: servicos, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: ['servicos'],
    queryFn: servicosApi.list,
    refetchInterval: 30_000,
  })

  const online = servicos?.filter((s) => s.online).length ?? 0
  const total  = servicos?.length ?? 0

  const executar = useMutation({
    mutationFn: (nome: string) => servicosApi.executar(nome),
    onSuccess: (data, nome) => flash.mostrar('sucesso', data.mensagem, { chave: nome }),
    onError: (e, nome) => flash.mostrar('erro', apiErr(e, 'Não foi possível executar o serviço.'), { chave: nome }),
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">Serviços Monitorados</h1>
          {!isLoading && (
            <p className="text-sm text-slate-500 mt-0.5">
              {online}/{total} serviços online · atualiza a cada 30s
            </p>
          )}
        </div>
        <IconButton label="Atualizar lista" appearance="outline" onClick={() => qc.invalidateQueries({ queryKey: ['servicos'] })}>
          <RefreshCw size={15} className={isFetching ? 'animate-spin' : ''} />
        </IconButton>
      </div>

      {isError && !servicos && (
        <ErroCarregamento titulo="Não foi possível carregar os serviços." error={error} onRetry={() => refetch()} />
      )}

      {/* Summary cards */}
      {!isLoading && servicos && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-5">
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-xs text-slate-500 mb-1">Online</p>
            <p className="text-2xl font-bold text-green-500">{online}</p>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-xs text-slate-500 mb-1">Offline</p>
            <p className="text-2xl font-bold text-red-500">{total - online}</p>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-xs text-slate-500 mb-1">Total</p>
            <p className="text-2xl font-bold text-slate-700">{total}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-slate-200 p-5 animate-pulse">
              <div className="h-4 bg-slate-100 rounded w-1/2 mb-3" />
              <div className="h-3 bg-slate-100 rounded w-3/4" />
            </div>
          ))
        ) : servicos?.map((s) => (
          <div
            key={s.id}
            className={`bg-white rounded-xl border p-5 ${
              s.online ? 'border-green-200' : 'border-red-200'
            }`}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold text-slate-800">{s.nome}</h3>
                {s.mensagem && <p className="text-sm text-slate-500 mt-0.5">{s.mensagem}</p>}
              </div>
              <div className="flex items-center gap-2 shrink-0 ml-3">
                <IconButton
                  label={`Executar serviço ${s.nome}`}
                  tooltip="Executar serviço"
                  onClick={() => executar.mutate(s.nome)}
                  loading={executar.isPending && executar.variables === s.nome}
                  className="rounded-lg border border-slate-200 hover:bg-slate-50 hover:text-blue-500"
                >
                  <Play size={13} />
                </IconButton>
                {(() => {
                  const statusLabel = !s.status || s.status === 'OK' ? 'Online' : s.status
                  const badge = !s.online
                    ? { label: 'Offline',      cls: 'bg-red-100 text-red-700',    Icon: XCircle  }
                    : s.status === 'Em execução'
                    ? { label: 'Em execução',  cls: 'bg-amber-100 text-amber-700', Icon: Loader2  }
                    : { label: statusLabel,    cls: 'bg-green-100 text-green-700', Icon: CheckCircle }
                  return (
                    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${badge.cls}`}>
                      <badge.Icon size={12} className={s.status === 'Em execução' ? 'animate-spin' : ''} />
                      {badge.label}
                    </div>
                  )
                })()}
              </div>
            </div>

            {flash.flash?.chave === s.nome && <FlashBanner flash={flash.flash} compacto />}

            <div className="flex items-center gap-4 text-xs text-slate-500">
              <div className="flex items-center gap-1">
                <Clock size={11} />
                <span>Último heartbeat: {fmtDataHora(s.ultimo_heartbeat, 'Nunca')}</span>
              </div>
              <span>Timeout: {s.timeout_minutos}min</span>
            </div>
          </div>
        ))}
      </div>

      {!isLoading && !isError && !servicos?.length && (
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-400 text-sm">
          Nenhum serviço cadastrado
        </div>
      )}
    </div>
  )
}
