import { cn } from '@/lib/utils'

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Add the AI-active cyan outer glow. */
  glow?: boolean
}

/**
 * The signature "Clinical Glass" surface: translucent white, 20px backdrop
 * blur, faint border, 16px radius, soft glass shadow. See design.md.
 */
export function GlassCard({ glow, className, children, ...props }: GlassCardProps) {
  return (
    <div
      className={cn(
        'glassmorphism rounded-2xl shadow-glass-panel',
        glow && 'shadow-ai-glow',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}
