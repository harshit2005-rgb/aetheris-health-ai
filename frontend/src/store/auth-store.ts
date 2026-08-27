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
  /** True while the app is attempting to restore a session on load. */
  isRestoring: boolean
  setAuth: (user: User, accessToken: string, refreshToken?: string | null) => void
  logout: () => void
  setRestoring: (v: boolean) => void
}

/**
 * Auth store. Intentionally NOT persisted: the access token lives in
 * `tokenStore` (memory), the refresh token is stored alongside it (returned
 * in the backend response body), and `isAuthenticated` is derived state — not
 * a flag a visitor can write to localStorage to become an admin (defects F2, F3).
 */
export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  // If there's no refresh token in memory there's nothing to restore, so
  // skip the spinner entirely (avoids a full-screen flash on public pages).
  isRestoring: tokenStore.getRefreshToken() !== null,
  setAuth: (user, accessToken, refreshToken?: string | null) => {
    tokenStore.setAccessToken(accessToken)
    if (refreshToken !== undefined) {
      tokenStore.setRefreshToken(refreshToken)
    }
    set({ user, isAuthenticated: true })
  },
  logout: () => {
    tokenStore.clear()
    set({ user: null, isAuthenticated: false })
  },
  setRestoring: (v) => set({ isRestoring: v }),
}))
