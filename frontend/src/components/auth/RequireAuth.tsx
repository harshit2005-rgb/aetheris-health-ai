import { Navigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { Loader2 } from 'lucide-react'
import { useAuthStore } from '@/store/auth-store'

/**
 * Route guard for authenticated app screens.
 *
 * During session restoration (isRestoring = true), shows a loading spinner
 * instead of redirecting to /login — this prevents the "redirect flicker"
 * where protected pages briefly flash the login screen on reload (task 6).
 *
 * Once restoration completes:
 * - Authenticated users see their intended page.
 * - Unauthenticated users are sent to /login with the return location saved.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const isRestoring = useAuthStore((s) => s.isRestoring)
  const location = useLocation()

  // Still restoring — show spinner, don't redirect yet.
  if (isRestoring) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="text-secondary size-8 animate-spin" />
          <p className="font-body text-on-surface-variant text-sm">Loading…</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return <>{children}</>
}
