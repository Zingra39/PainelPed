import { useQuery } from '@tanstack/react-query'
import { BRAND } from '../../lib/cores'
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { FileStack } from 'lucide-react'
import { dashboardApi } from '../../api/dashboard'
import type { PeriodoFiltro } from '../../types'
import { GRID_STROKE, GRID_DASH, TICK_EIXO, TOOLTIP_CURSOR_BARRA, TOOLTIP_CONTENT, TOOLTIP_LABEL, opcoesDashboard } from './chartStyles'
import ChartCard, { GraficoErro, GraficoVazio } from './ChartCard'

// Cores da paleta oficial da marca — mesmas cores já usadas nos cards de KPI
// para Retornos/Espelhos/Cancelamentos Gerados, no topo do Dashboard.
const CORES = {
  retorno: '#2196F3',
  espelho: '#24D03E',
  cancelamento: '#E31C38',
}

const NOMES: Record<keyof typeof CORES, string> = {
  retorno: 'Retorno',
  espelho: 'Espelho',
  cancelamento: 'Cancelamento',
}

function formatarDataCurta(iso: string) {
  const [, mes, dia] = iso.split('-')
  return `${dia}/${mes}`
}

export default function ArquivosEnviadosPorDiaChart({ periodo }: { periodo: PeriodoFiltro }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['dashboard-arquivos-enviados-por-dia', periodo],
    queryFn: () => dashboardApi.arquivosEnviadosPorDia(periodo),
    ...opcoesDashboard,
  })

  const temDados = (data ?? []).some((d) => d.retorno + d.espelho + d.cancelamento > 0)

  return (
    <ChartCard
      titulo="Envio de Arquivos por Dia"
      subtitulo='Arquivos de Retorno, Espelho e Cancelamento na situação &quot;Enviado&quot;, pela data do pedido a que pertencem'
      icone={FileStack}
      cor={BRAND}
    >
      {isLoading ? (
        <GraficoVazio mensagem="Carregando…" />
      ) : isError && !data ? (
        <GraficoErro onRetry={() => refetch()} />
      ) : !temDados ? (
        <GraficoVazio mensagem="Nenhum arquivo enviado no período." icone={FileStack} />
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }} barCategoryGap={12}>
            <defs>
              {Object.entries(CORES).map(([key, cor]) => (
                <linearGradient key={key} id={`grad-${key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={cor} stopOpacity={0.95} />
                  <stop offset="100%" stopColor={cor} stopOpacity={0.6} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid vertical={false} stroke={GRID_STROKE} strokeDasharray={GRID_DASH} />
            <XAxis
              dataKey="data"
              tickFormatter={formatarDataCurta}
              tick={TICK_EIXO}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              allowDecimals={false}
              tick={TICK_EIXO}
              axisLine={false}
              tickLine={false}
              width={28}
            />
            <Tooltip
              cursor={TOOLTIP_CURSOR_BARRA}
              contentStyle={TOOLTIP_CONTENT}
              labelStyle={TOOLTIP_LABEL}
              labelFormatter={(v) => formatarDataCurta(String(v))}
              formatter={(value, name) => [value, NOMES[name as keyof typeof CORES] ?? name]}
            />
            <Legend
              formatter={(value: string) => (
                <span style={{ color: '#334155', fontSize: 12 }}>{NOMES[value as keyof typeof CORES] ?? value}</span>
              )}
              iconType="circle"
              iconSize={8}
            />
            <Bar dataKey="retorno" stackId="arquivos" fill="url(#grad-retorno)" radius={[0, 0, 0, 0]} maxBarSize={26} />
            <Bar dataKey="espelho" stackId="arquivos" fill="url(#grad-espelho)" radius={[0, 0, 0, 0]} maxBarSize={26} />
            <Bar dataKey="cancelamento" stackId="arquivos" fill="url(#grad-cancelamento)" radius={[6, 6, 0, 0]} maxBarSize={26} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  )
}
