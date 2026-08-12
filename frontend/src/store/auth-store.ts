import { create } from 'zustand'
import type { Permission, Role } from '@/lib/rbac'
import { tokenStore } from '@/services/tokenStore'

export interface User {
  id: string
  name: string
  email: string
  role: Role
  /** Permission codes issued by the server (spec / defect F5). */
  permissions: Permission[]
}

interface AuthState {
  user: User | null
  /** Derived, in-memory only. Never persisted, so it cannot be forged from
   *  devtools (defect F2). A reload drops it; the app re-auths via /auth/refresh. */
  isAuthenticated: boolean
  setAuth: (user: User, accessToken: string) => void
  logout: () => void
}

/**
 * Auth store. Intentionally NOT persisted: the access token lives in
 * `tokenStore` (memory), the refresh token is an HTTP-only cookie set by the
 * backend, and `isAuthenticated` is derived state — not a flag a visitor can
 * write to localStorage to become an admin (defects F2, F3).
 */
export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  setAuth: (user, accessToken) => {
    tokenStore.set(accessToken)
    set({ user, isAuthenticated: true })
  },
  logout: () => {
    tokenStore.clear()
    set({ user: null, isAuthenticated: false })
  },
}))
