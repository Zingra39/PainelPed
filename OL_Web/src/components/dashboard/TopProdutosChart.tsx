import { useQuery } from '@tanstack/react-query'
import {
  Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Package } from 'lucide-react'
import { dashboardApi } from '../../api/dashboard'
import type { PeriodoFiltro } from '../../types'
import { GRID_STROKE, GRID_DASH, TICK_EIXO, TICK_CATEGORIA, TOOLTIP_CURSOR_BARRA, TOOLTIP_CONTENT, TOOLTIP_LABEL, ROTULO_BARRA, RAIO_BARRA_HORIZONTAL, opcoesDashboard } from './chartStyles'
import ChartCard, { GraficoErro, GraficoVazio } from './ChartCard'
import type { TopProdutoItem } from '../../types'

const COR = '#EF7400' // laranja da paleta oficial

function rotuloProduto(item: TopProdutoItem) {
  if (item.descricao) return item.descricao
  return `EAN ${item.ean}`
}

export default function TopProdutosChart({ periodo }: { periodo: PeriodoFiltro }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['dashboard-top-produtos', periodo],
    queryFn: () => dashboardApi.topProdutos(periodo, 10),
    ...opcoesDashboard,
  })

  const dadosGrafico = (data ?? []).map((item) => ({ ...item, rotulo: rotuloProduto(item) }))
  const semDescricao = (data ?? []).some((item) => !item.descricao)

  return (
    <ChartCard
      titulo="Top 10 Produtos Mais Solicitados"
      subtitulo="Soma da quantidade solicitada nos itens de pedido do período"
      altura={340}
      icone={Package}
      cor={COR}
      rodape={
        semDescricao
          ? 'A descrição de alguns produtos não pôde ser buscada no ERP no momento — eles aparecem só com o EAN.'
          : undefined
      }
    >
      {isLoading ? (
        <GraficoVazio mensagem="Carregando…" />
      ) : isError && !data ? (
        <GraficoErro onRetry={() => refetch()} />
      ) : dadosGrafico.length === 0 ? (
        <GraficoVazio mensagem="Nenhum item de pedido no período." icone={Package} />
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={dadosGrafico}
            layout="vertical"
            margin={{ top: 4, right: 40, bottom: 4, left: 4 }}
            barCategoryGap={8}
          >
            <defs>
              <linearGradient id="gradProdutos" x1="0" y1="0" x2="1" y2="0">
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
              dataKey="rotulo"
              width={220}
              tick={TICK_CATEGORIA}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              cursor={TOOLTIP_CURSOR_BARRA}
              contentStyle={TOOLTIP_CONTENT}
              labelStyle={TOOLTIP_LABEL}
              formatter={(value) => [value, 'Qtd. solicitada']}
            />
            <Bar dataKey="quantidade_solicitada" radius={RAIO_BARRA_HORIZONTAL} maxBarSize={18} fill="url(#gradProdutos)">
              <LabelList dataKey="quantidade_solicitada" position="right" style={ROTULO_BARRA} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  )
}
