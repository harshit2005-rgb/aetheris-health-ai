import { RadialBar, RadialBarChart, PolarAngleAxis } from 'recharts'
import { cn } from '@/lib/utils'

interface RadialProgressProps {
  /** 0–100 */
  value: number
  size?: number
  /** Arc color (defaults to AI-electric cyan). */
  color?: string
  label: string
  sublabel: string
  className?: string
}

/**
 * A single-value progress ring built on Recharts, styled to sit on the
 * neomorphic "sunken track" surface. Rounded cap + soft drop-shadow give it
 * the extruded feel from the Stitch design.
 */
export function RadialProgress({
  value,
  size = 160,
  color = 'var(--color-secondary-container)',
  label,
  sublabel,
  className,
}: RadialProgressProps) {
  return (
    <div
      className={cn('neo-pressed relative rounded-full', className)}
      style={{ width: size, height: size }}
    >
      <RadialBarChart
        width={size}
        height={size}
        cx="50%"
        cy="50%"
        innerRadius="78%"
        outerRadius="100%"
        barSize={9}
        data={[{ value }]}
        startAngle={90}
        endAngle={-270}
      >
        <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
        <RadialBar
          dataKey="value"
          angleAxisId={0}
          cornerRadius={10}
          fill={color}
          background={{ fill: 'var(--color-surface-container-high)' }}
          isAnimationActive
          animationDuration={900}
          className="[filter:drop-shadow(1px_1px_2px_rgba(0,0,0,0.12))]"
        />
      </RadialBarChart>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display text-headline-md text-primary font-bold">{value}%</span>
        <span className="font-label text-label-caps text-outline mt-0.5">{sublabel}</span>
        <span className="sr-only">{label}</span>
      </div>
    </div>
  )
}
