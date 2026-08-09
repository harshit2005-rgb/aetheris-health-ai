import axios from 'axios'

/**
 * Central Axios instance for the Aetheris backend.
 * Base URL comes from VITE_API_URL; falls back to the Vite dev proxy at /api.
 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Attach the auth token (if any) to every request.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('aetheris.token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Surface auth failures centrally.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('aetheris.token')
      // Let route guards handle the redirect; just clear the stale token here.
    }
    return Promise.reject(error)
  },
)
