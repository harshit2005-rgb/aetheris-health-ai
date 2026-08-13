/** Standard API envelope — every backend response follows this shape (CLAUDE.md). */
export interface ApiResponse<T> {
  success: boolean
  data: T
  meta?: { pagination?: PaginationMeta }
  error?: { code: string; message: string; details?: unknown }
}

export interface PaginationMeta {
  page: number
  pageSize: number
  total: number
  totalPages: number
}

/** A list payload plus its pagination metadata, unwrapped for consumers. */
export interface Paginated<T> {
  items: T[]
  pagination: PaginationMeta
}

/** Thrown by the HTTP layer on a non-success response. Carries the backend code. */
export class ApiError extends Error {
  readonly code: string
  readonly status?: number
  readonly details?: unknown

  constructor(message: string, code = 'unknown', status?: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}
