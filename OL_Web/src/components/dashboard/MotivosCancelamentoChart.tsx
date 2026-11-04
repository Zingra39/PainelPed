import { useQuery } from '@tanstack/react-query'
import {
  Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { XCircle } from 'lucide-react'
import { dashboardApi } from '../../api/dashboard'
import type { PeriodoFiltro } from '../../types'
import { GRID_STROKE, GRID_DASH, TICK_EIXO, TICK_CATEGORIA, TOOLTIP_CURSOR_BARRA, TOOLTIP_CONTENT, TOOLTIP_LABEL, ROTULO_BARRA, RAIO_BARRA_HORIZONTAL, opcoesDashboard } from './chartStyles'
import ChartCard, { GraficoErro, GraficoVazio } from './ChartCard'

const COR = '#E31C38' // vermelho da paleta oficial — mesma cor do KPI "Cancelamentos Gerados"

export default function MotivosCancelamentoChart({ periodo }: { periodo: PeriodoFiltro }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['dashboard-motivos-cancelamento', periodo],
    queryFn: () => dashboardApi.motivosCancelamento(periodo),
    ...opcoesDashboard,
  })

  const dadosOrdenados = (data ?? []).slice(0, 10) // já vem ordenado desc do backend

  return (
    <ChartCard
      titulo="Motivos de Cancelamento de Pedidos"
      subtitulo="Ocorrências de validação dos pedidos do período, por motivo"
      altura={320}
      icone={XCircle}
      cor={COR}
      // rodape='Não existe hoje um status "Cancelado" atribuído automaticamente a um pedido — este gráfico usa as ocorrências de validação (Cliente, Condição, Produto, Pedido) como aproximação dos pedidos que não seguiram adiante.'
    >
      {isLoading ? (
        <GraficoVazio mensagem="Carregando…" />
      ) : isError && !data ? (
        <GraficoErro onRetry={() => refetch()} />
      ) : dadosOrdenados.length === 0 ? (
        <GraficoVazio mensagem="Nenhuma ocorrência registrada no período." icone={XCircle} />
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={dadosOrdenados}
            layout="vertical"
            margin={{ top: 4, right: 36, bottom: 4, left: 4 }}
            barCategoryGap={10}
          >
            <defs>
              <linearGradient id="gradMotivos" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor={COR} stopOpacity={0.45} />
                <stop offset="100%" stopColor={COR} stopOpacity={0.95} />
              </linearGradient>
            </defs>
            <CartesianGrid horizontal={false} stroke={GRID_STROKE} strokeDasharray={GRID_DASH} />
            <XAxis
              type="number"
              allowDecimals={false}
              tick={TICK_EIXO}
              axisLine={false}
              tickLine={false}
              tickCount={4}
            />
            <YAxis
              type="category"
              dataKey="motivo"
              width={190}
              tick={TICK_CATEGORIA}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              cursor={TOOLTIP_CURSOR_BARRA}
              contentStyle={TOOLTIP_CONTENT}
              labelStyle={TOOLTIP_LABEL}
              formatter={(value) => [value, 'Ocorrências']}
            />
            <Bar dataKey="total" radius={RAIO_BARRA_HORIZONTAL} maxBarSize={20} fill="url(#gradMotivos)">
              <LabelList dataKey="total" position="right" style={ROTULO_BARRA} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  )
}
