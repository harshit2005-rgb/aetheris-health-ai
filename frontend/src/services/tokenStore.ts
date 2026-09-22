/**
 * In-memory access + refresh token store.
 *
 * Deliberately NOT localStorage: the root CLAUDE.md requires the access token
 * to live in memory and the refresh token to be treated as a credential
 * (never logged, never persisted to client-accessible storage).
 *
 * The backend returns both tokens in the response body (not HTTP-only cookies),
 * so we store them here. A page reload drops both; the app shows the login
 * screen. This matches the approved token strategy from the backend contract.
 */
let accessToken: string | null = null
let refreshToken: string | null = null

export const tokenStore = {
  getAccessToken: () => accessToken,
  getRefreshToken: () => refreshToken,

  setAccessToken: (token: string | null) => {
    accessToken = token
  },

  setRefreshToken: (token: string | null) => {
    refreshToken = token
  },

  /** Set both tokens at once (typical after login or refresh). */
  setTokens: (access: string | null, refresh: string | null) => {
    accessToken = access
    refreshToken = refresh
  },

  clear: () => {
    accessToken = null
    refreshToken = null
  },
}
