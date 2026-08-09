import { cn } from '@/lib/utils'

interface IconProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Material Symbols Outlined ligature name, e.g. "monitor_heart". */
  name: string
  /** Render the filled variant. */
  filled?: boolean
}

/**
 * Thin wrapper around Google Material Symbols (loaded in index.html).
 * Usage: <Icon name="smart_toy" filled className="text-secondary" />
 */
export function Icon({ name, filled, className, ...props }: IconProps) {
  return (
    <span
      aria-hidden
      className={cn('msym select-none', filled && 'fill', className)}
      {...props}
    >
      {name}
    </span>
  )
}
