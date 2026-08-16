import {
  Area,
  AreaChart as ReAreaChart,
  Bar,
  BarChart as ReBarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart as ReLineChart,
  Pie,
  PieChart as RePieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { AXIS_PROPS, CHART_COLORS, GRID_STROKE, TOOLTIP_STYLE } from './chart-theme'

export interface Series {
  key: string
  label?: string
  color?: string
}

interface CartesianChartProps {
  data: Array<Record<string, string | number>>
  xKey: string
  series: Series[]
  height?: number
  /** Hide the legend when a single series makes it redundant. */
  showLegend?: boolean
}

const legendStyle = { fontFamily: 'var(--font-label)', fontSize: 12 }

function color(s: Series, i: number) {
  return s.color ?? CHART_COLORS[i % CHART_COLORS.length]
}

export function LineChart({ data, xKey, series, height = 280, showLegend = true }: CartesianChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ReLineChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey={xKey} {...AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={40} />
        <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ stroke: GRID_STROKE }} />
        {showLegend && series.length > 1 && <Legend wrapperStyle={legendStyle} />}
        {series.map((s, i) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label ?? s.key}
            stroke={color(s, i)}
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4 }}
          />
        ))}
      </ReLineChart>
    </ResponsiveContainer>
  )
}

export function AreaChart({ data, xKey, series, height = 280, showLegend = true }: CartesianChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ReAreaChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <defs>
          {series.map((s, i) => (
            <linearGradient key={s.key} id={`fill-${s.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color(s, i)} stopOpacity={0.35} />
              <stop offset="95%" stopColor={color(s, i)} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey={xKey} {...AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={40} />
        <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ stroke: GRID_STROKE }} />
        {showLegend && series.length > 1 && <Legend wrapperStyle={legendStyle} />}
        {series.map((s, i) => (
          <Area
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label ?? s.key}
            stroke={color(s, i)}
            strokeWidth={2.5}
            fill={`url(#fill-${s.key})`}
          />
        ))}
      </ReAreaChart>
    </ResponsiveContainer>
  )
}

export function BarChart({ data, xKey, series, height = 280, showLegend = true }: CartesianChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ReBarChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey={xKey} {...AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={40} />
        <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'var(--color-surface-container)' }} />
        {showLegend && series.length > 1 && <Legend wrapperStyle={legendStyle} />}
        {series.map((s, i) => (
          <Bar
            key={s.key}
            dataKey={s.key}
            name={s.label ?? s.key}
            fill={color(s, i)}
            radius={[6, 6, 0, 0]}
          />
        ))}
      </ReBarChart>
    </ResponsiveContainer>
  )
}

interface PieDatum {
  name: string
  value: number
}

interface PieChartProps {
  data: PieDatum[]
  height?: number
  /** Inner radius > 0 renders a donut. */
  donut?: boolean
}

export function PieChart({ data, height = 280, donut = true }: PieChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RePieChart>
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Legend wrapperStyle={legendStyle} />
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={donut ? '55%' : 0}
          outerRadius="80%"
          paddingAngle={donut ? 2 : 0}
        >
          {data.map((d, i) => (
            <Cell key={d.name} fill={CHART_COLORS[i % CHART_COLORS.length]} />
          ))}
        </Pie>
      </RePieChart>
    </ResponsiveContainer>
  )
}
