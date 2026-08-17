import { cn } from '@/lib/utils'
import lockup from '@/assets/logo-lockup.png'
import mark from '@/assets/logo-mark.png'

interface LogoProps {
  /** "lockup" = full mark + "Aetheris Health AI" wordmark; "mark" = icon only. */
  variant?: 'lockup' | 'mark'
  className?: string
}

/**
 * Official Aetheris Health AI logo. The wordmark is baked into the lockup
 * artwork, so it already carries the brand name — no separate text needed.
 */
export function Logo({ variant = 'lockup', className }: LogoProps) {
  return (
    <img
      src={variant === 'mark' ? mark : lockup}
      alt="Aetheris Health AI"
      // The brand artwork is navy ink + cyan, which loses contrast on dark
      // surfaces. Until a light logo asset ships, render it as a white monochrome
      // in dark mode so the wordmark stays legible.
      className={cn('block w-auto select-none dark:brightness-0 dark:invert', className)}
      draggable={false}
    />
  )
}
