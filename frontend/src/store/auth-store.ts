import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface User {
  id: string
  name: string
  email: string
  role: 'clinician' | 'admin' | 'patient'
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  setAuth: (user: User, token: string) => void
  logout: () => void
}

/**
 * Global auth store. The token is mirrored into localStorage under
 * `aetheris.token` so the Axios interceptor can read it outside React.
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      setAuth: (user, token) => {
        localStorage.setItem('aetheris.token', token)
        set({ user, token, isAuthenticated: true })
      },
      logout: () => {
        localStorage.removeItem('aetheris.token')
        set({ user: null, token: null, isAuthenticated: false })
      },
    }),
    { name: 'aetheris.auth' },
  ),
)
