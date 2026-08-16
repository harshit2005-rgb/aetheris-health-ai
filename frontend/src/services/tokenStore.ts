/**
 * In-memory access token. Deliberately NOT localStorage: the root CLAUDE.md
 * requires the access token to live in memory (refresh comes from an HTTP-only
 * cookie the backend sets). Keeping it here means a page reload drops the token,
 * and the app re-establishes the session via /auth/refresh on load.
 */
let accessToken: string | null = null

export const tokenStore = {
  get: () => accessToken,
  set: (token: string | null) => {
    accessToken = token
  },
  clear: () => {
    accessToken = null
  },
}
