import { useQuery } from '@tanstack/react-query'
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { TrendingUp } from 'lucide-react'
import { dashboardApi } from '../../api/dashboard'
import type { PeriodoFiltro } from '../../types'
import { GRID_STROKE, GRID_DASH, TICK_EIXO, TOOLTIP_CURSOR_LINHA, TOOLTIP_CONTENT, TOOLTIP_LABEL, opcoesDashboard } from './chartStyles'
import ChartCard, { GraficoErro, GraficoVazio } from './ChartCard'

const COR = '#2196F3' // azul da paleta oficial

function formatarDataCurta(iso: string) {
  const [, mes, dia] = iso.split('-')
  return `${dia}/${mes}`
}

export default function PedidosFaturadosPorDiaChart({ periodo }: { periodo: PeriodoFiltro }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['dashboard-pedidos-faturados-por-dia', periodo],
    queryFn: () => dashboardApi.pedidosFaturadosPorDia(periodo),
    ...opcoesDashboard,
  })

  const temDados = (data ?? []).some((d) => d.total > 0)

  return (
    <ChartCard
      titulo="Pedidos Faturados por Dia"
      subtitulo='Pedidos com status "Faturado" no ERP, por data do pedido'
      icone={TrendingUp}
      cor={COR}
      // rodape='Depende do status "Faturado" ser atualizado no pedido — hoje nenhum processo automático deste sistema faz essa atualização, então o gráfico pode aparecer vazio até essa sincronização com o ERP existir.'
    >
      {isLoading ? (
        <GraficoVazio mensagem="Carregando…" />
      ) : isError && !data ? (
        <GraficoErro onRetry={() => refetch()} />
      ) : !temDados ? (
        <GraficoVazio mensagem="Nenhum pedido faturado no período." icone={TrendingUp} />
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
            <defs>
              <linearGradient id="gradPedidos" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COR} stopOpacity={0.32} />
                <stop offset="100%" stopColor={COR} stopOpacity={0} />
              </linearGradient>
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
              cursor={TOOLTIP_CURSOR_LINHA}
              contentStyle={TOOLTIP_CONTENT}
              labelStyle={TOOLTIP_LABEL}
              labelFormatter={(v) => formatarDataCurta(String(v))}
              formatter={(value) => [value, 'Pedidos faturados']}
            />
            <Area
              type="monotone"
              dataKey="total"
              stroke={COR}
              strokeWidth={2.5}
              fill="url(#gradPedidos)"
              dot={{ r: 3, fill: COR, strokeWidth: 2, stroke: '#fff' }}
              activeDot={{ r: 5, fill: COR, strokeWidth: 2, stroke: '#fff' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  )
}
