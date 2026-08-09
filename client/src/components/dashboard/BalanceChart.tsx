import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { PortfolioSeries } from '../../lib/types'
import { formatCompactCurrency, formatCurrency } from '../../lib/format'

const PRIMARY = '#006041'
const GRID = '#bec9c1'
const AXIS_TEXT = '#3f4943'

interface BalanceChartProps {
  series: PortfolioSeries
}

export function BalanceChart({ series }: BalanceChartProps) {
  const padding = (series.high - series.low) * 0.25 || series.high * 0.01
  const tickInterval = Math.max(1, Math.floor(series.points.length / 6)) - 1

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={series.points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="balanceGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={PRIMARY} stopOpacity={0.24} />
            <stop offset="100%" stopColor={PRIMARY} stopOpacity={0} />
          </linearGradient>
        </defs>

        <CartesianGrid stroke={GRID} strokeOpacity={0.6} vertical={false} />

        <XAxis
          dataKey="label"
          interval={tickInterval}
          tickLine={false}
          axisLine={{ stroke: GRID }}
          tick={{ fill: AXIS_TEXT, fontSize: 10 }}
          minTickGap={12}
        />
        <YAxis
          domain={[series.low - padding, series.high + padding]}
          width={64}
          tickLine={false}
          axisLine={false}
          tick={{ fill: AXIS_TEXT, fontSize: 10 }}
          tickFormatter={(value: number) => formatCompactCurrency(value)}
        />

        <Tooltip
          cursor={{ stroke: PRIMARY, strokeDasharray: '4 4' }}
          contentStyle={{
            backgroundColor: '#ffffff',
            border: `1px solid ${GRID}`,
            borderRadius: 8,
            fontSize: 12,
          }}
          labelStyle={{ color: AXIS_TEXT, fontWeight: 700 }}
          formatter={(value) => [formatCurrency(Number(value)), 'Balance']}
        />

        <Area
          type="monotone"
          dataKey="value"
          stroke={PRIMARY}
          strokeWidth={2}
          fill="url(#balanceGradient)"
          activeDot={{ r: 4, fill: '#fcf9f8', stroke: PRIMARY, strokeWidth: 2 }}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
