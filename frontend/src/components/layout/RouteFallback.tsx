import { Loader2 } from 'lucide-react'

/**
 * Full-viewport fallback shown while a lazily-loaded route chunk is fetched.
 * Intentionally minimal so it costs nothing in the initial bundle.
 */
export function RouteFallback() {
  return (
    <div
      className="flex min-h-screen items-center justify-center bg-surface"
      role="status"
      aria-live="polite"
    >
      <Loader2 className="size-6 animate-spin text-primary" aria-hidden />
      <span className="sr-only">Loading…</span>
    </div>
  )
}
