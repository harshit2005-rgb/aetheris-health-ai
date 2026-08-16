import { AxiosError, type AxiosRequestConfig } from 'axios'
import { api } from '@/lib/api'
import { ApiError, type ApiResponse, type Paginated } from '@/api/types'

/**
 * Typed wrappers around the Axios instance. They unwrap the `{ success, data }`
 * envelope and throw a typed {@link ApiError} on failure — components and hooks
 * only ever see domain data (CLAUDE.md).
 */

function toApiError(err: unknown): ApiError {
  if (err instanceof AxiosError) {
    const body = err.response?.data as ApiResponse<unknown> | undefined
    return new ApiError(
      body?.message ?? err.message,
      body?.error_code ?? 'network_error',
      err.response?.status,
      body?.errors,
    )
  }
  return new ApiError(err instanceof Error ? err.message : 'Unexpected error')
}

async function request<T>(config: AxiosRequestConfig): Promise<T> {
  try {
    const res = await api.request<ApiResponse<T>>(config)
    return res.data.data
  } catch (err) {
    throw toApiError(err)
  }
}

/** GET that returns items + pagination together, reading `metadata.pagination`. */
async function getPaginated<T>(url: string, config?: AxiosRequestConfig): Promise<Paginated<T>> {
  try {
    const res = await api.get<ApiResponse<T[]>>(url, config)
    const wire = res.data.metadata?.pagination
    if (!wire) throw new ApiError('Response is missing pagination metadata', 'bad_response')
    return {
      items: res.data.data,
      pagination: {
        page: wire.page,
        pageSize: wire.page_size,
        total: wire.total_records,
        totalPages: wire.total_pages,
      },
    }
  } catch (err) {
    throw err instanceof ApiError ? err : toApiError(err)
  }
}

export const http = {
  get: <T>(url: string, config?: AxiosRequestConfig) => request<T>({ ...config, url, method: 'get' }),
  getPaginated,
  post: <T>(url: string, body?: unknown, config?: AxiosRequestConfig) =>
    request<T>({ ...config, url, method: 'post', data: body }),
  patch: <T>(url: string, body?: unknown, config?: AxiosRequestConfig) =>
    request<T>({ ...config, url, method: 'patch', data: body }),
  put: <T>(url: string, body?: unknown, config?: AxiosRequestConfig) =>
    request<T>({ ...config, url, method: 'put', data: body }),
  delete: <T>(url: string, config?: AxiosRequestConfig) =>
    request<T>({ ...config, url, method: 'delete' }),
}
