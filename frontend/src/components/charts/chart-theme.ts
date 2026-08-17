/**
 * Shared Recharts theming for Clinical Glass charts. The palette maps to the
 * --color-chart-* tokens (cyan/teal/navy family) defined in index.css.
 */
export const CHART_COLORS = [
  'var(--color-chart-1)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
  'var(--color-chart-4)',
  'var(--color-chart-5)',
] as const

export const AXIS_PROPS = {
  stroke: 'var(--color-outline)',
  fontSize: 12,
  tickLine: false,
  axisLine: false,
} as const

export const GRID_STROKE = 'var(--color-outline-variant)'

export const TOOLTIP_STYLE = {
  borderRadius: '0.75rem',
  border: '1px solid var(--color-outline-variant)',
  background: 'var(--color-surface-container-lowest)',
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  color: 'var(--color-on-surface)',
} as const
