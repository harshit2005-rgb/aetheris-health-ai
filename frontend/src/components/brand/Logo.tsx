import { cn } from '@/lib/utils'
import mark from '@/assets/logo-mark.png'

interface LogoProps {
  /** "lockup" = icon mark + "Atheris Health AI" wordmark; "mark" = icon only. */
  variant?: 'lockup' | 'mark'
  className?: string
}

// The brand artwork is navy ink + cyan, which loses contrast on dark surfaces.
// Until a light logo asset ships, render the mark as a white monochrome in dark
// mode so it stays legible.
const MARK_TONE = 'dark:brightness-0 dark:invert'

/**
 * Atheris Health AI logo.
 *
 * The lockup is the icon mark with the name set as live text beside it, drawn
 * in one SVG so it scales from its height (`h-10`) exactly as the old
 * single-image lockup did. The original lockup artwork (`logo-lockup.png`) has
 * an older spelling of the name drawn into the image, so it is not used; swap
 * this for a single image again once a corrected lockup is supplied.
 */
export function Logo({ variant = 'lockup', className }: LogoProps) {
  if (variant === 'mark') {
    return (
      <img
        src={mark}
        alt="Atheris Health AI"
        className={cn('block w-auto select-none', MARK_TONE, className)}
        draggable={false}
      />
    )
  }

  return (
    <svg
      viewBox="0 0 300 100"
      role="img"
      aria-label="Atheris Health AI"
      className={cn('text-primary block w-auto select-none', className)}
    >
      <image href={mark} x="0" y="0" width="100" height="100" className={MARK_TONE} />
      <text x="112" y="52" fontSize="46" fontWeight="800" letterSpacing="-1" fill="currentColor">
        Atheris
      </text>
      <text x="114" y="86" fontSize="27" fontWeight="500" fill="currentColor">
        Health AI
      </text>
    </svg>
  )
}
