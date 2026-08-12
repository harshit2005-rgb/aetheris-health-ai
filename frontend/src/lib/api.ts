import axios, { type InternalAxiosRequestConfig } from 'axios'
import { tokenStore } from '@/services/tokenStore'
import { useAuthStore } from '@/store/auth-store'

/**
 * Central Axios instance. `withCredentials` lets the browser send the HTTP-only
 * refresh cookie to /auth/refresh (the access token itself is attached from
 * memory below).
 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

// Attach the in-memory access token to every request.
api.interceptors.request.use((config) => {
  const token = tokenStore.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

type RetriableConfig = InternalAxiosRequestConfig & { _retry?: boolean }

// Serialize concurrent refreshes behind a single in-flight promise: the backend
// revokes all sessions on refresh-token reuse, so two parallel refreshes would
// log the user out everywhere (defect F4).
let refreshing: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  // TODO(backend): POST /auth/refresh reads the HTTP-only refresh cookie and
  // returns a new access token in the standard envelope.
  try {
    const { data } = await api.post('/auth/refresh')
    const token: string | null = data?.data?.access_token ?? null
    tokenStore.set(token)
    return token
  } catch {
    tokenStore.clear()
    return null
  }
}

// On 401: try one refresh, retry the original request, and only hard-logout if
// the refresh itself fails (defect F4).
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as RetriableConfig | undefined
    const isRefreshCall = original?.url?.includes('/auth/refresh')

    if (error.response?.status === 401 && original && !original._retry && !isRefreshCall) {
      original._retry = true
      refreshing = refreshing ?? refreshAccessToken()
      const token = await refreshing
      refreshing = null

      if (token) {
        original.headers.Authorization = `Bearer ${token}`
        return api(original)
      }
      // Refresh failed: clear session so route guards send the user to /login.
      useAuthStore.getState().logout()
    }
    return Promise.reject(error)
  },
)
