import { useState } from 'react'
import { BRAND, BRAND_DARK, NAVY } from '../lib/cores'
import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '../api/dashboard'
import { opcoesDashboard } from '../components/dashboard/chartStyles'
import ErroCarregamento from '../components/ErroCarregamento'
import { useAuth } from '../contexts/AuthContext'
import type { PeriodoFiltro } from '../types'
import {
  InboxIcon, FileDown, AlertTriangle, FileText, Printer, XCircle, SendHorizontal,
} from 'lucide-react'
import MotivosCancelamentoChart from '../components/dashboard/MotivosCancelamentoChart'
// Ocultos por hora, a pedido — reativar importando e voltando a renderizar:
// import ArquivosEnviadosPorDiaChart from '../components/dashboard/ArquivosEnviadosPorDiaChart'
// import PedidosFaturadosPorDiaChart from '../components/dashboard/PedidosFaturadosPorDiaChart'
// import TopProdutosChart from '../components/dashboard/TopProdutosChart'
import dispfarmWatermark from '../assets/DISPFARM BRANCA.png'
import Tooltip from '../components/Tooltip'

/** Formata um Date no padrão YYYY-MM-DD usado pelos <input type="date"> e pela
 *  API. Monta a partir dos componentes LOCAIS de propósito: toISOString()
 *  converte para UTC e viraria o dia para quem abre o painel à noite (UTC-3). */
function paraISO(d: Date) {
  const ano = d.getFullYear()
  const mes = String(d.getMonth() + 1).padStart(2, '0')
  const dia = String(d.getDate()).padStart(2, '0')
  return `${ano}-${mes}-${dia}`
}

/** Intervalo inicial do painel: do primeiro dia do mês corrente até hoje. */
function periodoPadrao(): PeriodoFiltro {
  const hoje = new Date()
  const primeiroDoMes = new Date(hoje.getFullYear(), hoje.getMonth(), 1)
  return { data_inicio: paraISO(primeiroDoMes), data_fim: paraISO(hoje) }
}

const CARD_CFG = [
  {
    key: 'total_recebidos',
    label: 'Arquivos Recebidos',
    icon: InboxIcon,
    color: '#2196F3',
    // Único card medido pela data de download no FTP: a tabela
    // arquivo_baixado_ftp não tem vínculo com pedido, então não há
    // data_pedido para ancorar o recorte como nos demais.
    dica: 'Contado pela data de download no FTP — os demais cards usam a data do pedido.',
  },
  { key: 'total_importados',             label: 'Pedidos Importados',       icon: FileDown,       color: BRAND },
  { key: 'total_pendentes',              label: 'Pedido para Verificar',    icon: AlertTriangle,  color: '#FF9C12' },
  { key: 'total_prontos_transmissao',    label: 'Prontos para Transmissão',  icon: SendHorizontal, color: NAVY },
  { key: 'total_retornos_gerados',       label: 'Retornos Enviados',          icon: FileText,       color: BRAND_DARK },
  { key: 'total_espelhos_gerados',       label: 'Pedidos Faturados',          icon: Printer,        color: '#24D03E' },
  { key: 'total_cancelamentos_gerados',  label: 'Pedidos Cancelados',     icon: XCircle,        color: '#E31C38' },
] as const

/** Converte um hex da paleta em rgba() para usar como fundo translúcido dos badges de ícone. */
function hexToRgba(hex: string, alpha: number) {
  const clean = hex.replace('#', '')
  const bigint = parseInt(clean, 16)
  const r = (bigint >> 16) & 255
  const g = (bigint >> 8) & 255
  const b = bigint & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export default function Dashboard() {
  const { user } = useAuth()
  const [periodo, setPeriodo] = useState<PeriodoFiltro>(periodoPadrao)

  const { data: cards, isLoading: cardsLoading, isError: cardsErro, error: cardsError, refetch: recarregarCards } = useQuery({
    queryKey: ['dashboard-cards', periodo],
    queryFn: () => dashboardApi.cards(periodo),
    ...opcoesDashboard,
  })

  /** Mantém o intervalo coerente: mexer numa ponta nunca deixa início > fim. */
  function alterarPeriodo(campo: keyof PeriodoFiltro, valor: string) {
    if (!valor) return
    setPeriodo((p) => {
      if (campo === 'data_inicio') {
        return { data_inicio: valor, data_fim: valor > p.data_fim ? valor : p.data_fim }
      }
      return { data_inicio: valor < p.data_inicio ? valor : p.data_inicio, data_fim: valor }
    })
  }

  const primeiroNome = user?.nome?.split(' ')[0] ?? 'usuário'

  return (
    <div>
      {/* Hero — boas-vindas + filtro de período em destaque */}
      <div
        className="relative overflow-hidden rounded-2xl mb-6"
        style={{ background: `linear-gradient(135deg, ${NAVY} 0%, ${BRAND_DARK} 100%)` }}
      >
        <img
          src={dispfarmWatermark}
          alt=""
          aria-hidden="true"
          className="pointer-events-none select-none absolute -right-4 -top-6 h-32 sm:h-44 md:h-52 w-auto opacity-15"
        />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse 60% 90% at 100% 0%, rgba(33,150,243,0.20) 0%, transparent 70%)' }}
        />

        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between p-5 sm:p-7">
          <div>
            <span className="inline-block text-[11px] font-semibold tracking-wide uppercase text-[#2196F3] bg-white/10 px-2.5 py-1 rounded-full mb-3">
              Painel de Controle
            </span>
            <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Olá, {primeiroNome}
            </h1>
            <p className="text-sm text-white/55 mt-1.5 max-w-md">
              Acompanhe o desempenho operacional do fluxo de pedidos e arquivos — atualizado automaticamente a cada minuto.
            </p>
          </div>

          <div className="flex flex-col gap-1.5 sm:items-end">
            <span className="text-[11px] font-medium text-white/40 uppercase tracking-wide">
              DATA DO PEDIDO
            </span>
            <div className="flex items-end gap-2 bg-white/10 backdrop-blur-sm rounded-xl p-2 flex-wrap">
              <label className="flex flex-col gap-1">
                <span className="text-[10px] font-medium text-white/45 uppercase tracking-wide">De</span>
                <input
                  type="date"
                  value={periodo.data_inicio}
                  max={periodo.data_fim}
                  onChange={(e) => alterarPeriodo('data_inicio', e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg bg-white/95 text-slate-700 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-[#2196F3]"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[10px] font-medium text-white/45 uppercase tracking-wide">Até</span>
                <input
                  type="date"
                  value={periodo.data_fim}
                  min={periodo.data_inicio}
                  onChange={(e) => alterarPeriodo('data_fim', e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg bg-white/95 text-slate-700 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-[#2196F3]"
                />
              </label>
              <button
                type="button"
                onClick={() => setPeriodo(periodoPadrao())}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white/70 hover:text-white hover:bg-white/10 transition-colors"
              >
                Mês atual
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Falha nos indicadores (Q1 da auditoria): antes os cards mostravam 0,
          que se confunde com "não houve pedidos" no período. */}
      {cardsErro && !cards && (
        <ErroCarregamento titulo="Não foi possível carregar os indicadores." error={cardsError} onRetry={() => recarregarCards()} />
      )}

      {/* Cards de KPI */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-7 gap-3 md:gap-4">
        {CARD_CFG.map(({ key, label, icon: Icon, color, ...resto }) => (
          <Tooltip key={key} label={'dica' in resto ? resto.dica : undefined} className="w-full">
          <div
            className="group relative w-full bg-white rounded-2xl border border-slate-200/70 p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 overflow-hidden"
          >
            <span className="absolute inset-x-0 top-0 h-1" style={{ background: color }} aria-hidden="true" />
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center mb-3 transition-transform duration-200 group-hover:scale-110"
              style={{ backgroundColor: hexToRgba(color, 0.12) }}
            >
              <Icon size={17} style={{ color }} />
            </div>
            {cardsLoading ? (
              <div className="h-7 w-12 rounded-md bg-slate-100 animate-pulse mb-1" />
            ) : (
              <p className="text-2xl font-bold text-slate-800 tabular-nums leading-none">
                {cards ? (cards[key as keyof typeof cards] ?? 0) : '—'}
              </p>
            )}
            <p className="text-xs text-slate-500 mt-1.5 leading-snug">{label}</p>
          </div>
          </Tooltip>
        ))}
      </div>

      {/* Gráficos */}
      <div className="mt-8 mb-3">
        <h2 className="text-base font-semibold text-slate-800">Análises</h2>
        <p className="text-xs text-slate-500 mt-0.5">Tendências e distribuições do período selecionado</p>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-1 gap-4">
        <MotivosCancelamentoChart periodo={periodo} />
        {/* "Envio de Arquivos por Dia" e "Pedidos Faturados por Dia" ocultos
            por hora, a pedido — ver imports comentados acima. */}
        {/* <TopProdutosChart periodo={periodo} /> */}
      </div>
    </div>
  )
}
