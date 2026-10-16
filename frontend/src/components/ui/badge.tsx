import type { ComponentProps } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'font-label text-label-caps inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 whitespace-nowrap',
  {
    variants: {
      variant: {
        neutral: 'bg-surface-container-high text-on-surface-variant',
        primary: 'bg-primary-container/10 text-primary',
        accent: 'bg-secondary/10 text-secondary',
        success: 'bg-stable/10 text-stable',
        warning: 'bg-amber-500/10 text-amber-600',
        critical: 'bg-critical/10 text-critical',
        error: 'bg-error-container text-on-error-container',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
)

interface BadgeProps extends ComponentProps<'span'>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
