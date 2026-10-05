import { createElement, type ReactNode } from 'react'
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios'
import { api } from '@/lib/api'
import { tokenStore } from '@/services/tokenStore'
import { ApiError } from '@/api/types'
import { toAppointmentQuery, useBookAppointment, type BookAppointmentInput } from './appointments'

/**
 * The API reads `date`, `status` and `type` (docs/18-API_CONTRACTS.md §5.3)
 * and ignores query parameters it does not know. So a wrong name is not an
 * error — it is an unfiltered list that looks like it worked.
 */
describe('toAppointmentQuery', () => {
  it('sends the filter names the API actually reads', () => {
    const query = toAppointmentQuery({
      appointment_date: '2030-01-07',
      appointment_status: 'booked',
      appointment_type: 'walk_in',
    })

    expect(query).toMatchObject({ date: '2030-01-07', status: 'booked', type: 'walk_in' })
    expect(query).not.toHaveProperty('appointment_date')
    expect(query).not.toHaveProperty('appointment_status')
    expect(query).not.toHaveProperty('appointment_type')
  })

  it('passes the other parameters through unchanged', () => {
    const query = toAppointmentQuery({ patient_id: 'p1', doctor_id: 'd1', page: 2, page_size: 50 })

    expect(query).toMatchObject({ patient_id: 'p1', doctor_id: 'd1', page: 2, page_size: 50 })
  })

  it('sends no timezone offset — the server uses the hospital timezone', () => {
    // PR #29 review finding 7: a whole-hour offset rounded India's +5:30 to +6.
    expect(toAppointmentQuery({ appointment_date: '2030-01-07' })).not.toHaveProperty(
      'tz_offset_hours',
    )
  })
})

/**
 * `POST /appointments` is rejected with 422 without an `Idempotency-Key`
 * (docs/18-API_CONTRACTS.md §5.2). These run the real hook, `http` wrapper and
 * Axios instance, and replace only the network adapter — so they assert on the
 * request that would actually leave the browser.
 */
describe('useBookAppointment', () => {
  const input: BookAppointmentInput = {
    patient_id: '3f1c6c1e-2c3d-4a5b-8c7d-9e0f1a2b3c4d',
    doctor_id: '8a7b6c5d-4e3f-2a1b-0c9d-8e7f6a5b4c3d',
    scheduled_start: '2030-01-07T04:00:00.000Z',
    scheduled_end: '2030-01-07T04:15:00.000Z',
    type: 'new',
  }

  const originalAdapter = api.defaults.adapter
  let sent: InternalAxiosRequestConfig[]
  let respond: (config: InternalAxiosRequestConfig) => { status: number; data: unknown } | 'network'

  const keyOf = (config: InternalAxiosRequestConfig) => config.headers.get('Idempotency-Key')

  beforeEach(() => {
    sent = []
    respond = () => ({ status: 201, data: { success: true, message: 'ok', data: { id: 'a1' } } })
    const adapter: AxiosAdapter = async (config) => {
      sent.push(config)
      const outcome = respond(config)
      if (outcome === 'network') throw new AxiosError('Network Error', 'ERR_NETWORK', config)
      const response = { ...outcome, statusText: '', headers: {}, config }
      if (outcome.status >= 400) {
        throw new AxiosError('Request failed', 'ERR_BAD_REQUEST', config, null, response)
      }
      return response
    }
    api.defaults.adapter = adapter
    tokenStore.setTokens('access-token', null)
  })

  afterEach(() => {
    api.defaults.adapter = originalAdapter
    tokenStore.clear()
  })

  function renderBooking() {
    const client = new QueryClient()
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children)
    return renderHook(() => useBookAppointment(), { wrapper })
  }

  it('posts the booking with an Idempotency-Key the API accepts', async () => {
    const { result } = renderBooking()

    await act(() => result.current.mutateAsync(input))

    expect(sent).toHaveLength(1)
    const [request] = sent
    expect(request.method).toBe('post')
    expect(`${request.baseURL}${request.url}`).toBe('/api/v1/appointments')
    expect(JSON.parse(request.data as string)).toEqual(input)
    expect(request.headers.get('Content-Type')).toBe('application/json')
    expect(request.headers.get('Authorization')).toBe('Bearer access-token')
    // The route declares the header with min_length=8, max_length=200.
    const key = keyOf(request)
    expect(typeof key).toBe('string')
    expect((key as string).length).toBeGreaterThanOrEqual(8)
    expect((key as string).length).toBeLessThanOrEqual(200)
  })

  it('reuses the key when the same booking is resubmitted after a failure', async () => {
    const { result } = renderBooking()
    respond = () => 'network'

    await act(async () => {
      await expect(result.current.mutateAsync(input)).rejects.toBeInstanceOf(ApiError)
    })
    respond = () => ({ status: 200, data: { success: true, message: 'replay', data: { id: 'a1' } } })
    await act(() => result.current.mutateAsync({ ...input }))

    expect(sent).toHaveLength(2)
    expect(keyOf(sent[1])).toBe(keyOf(sent[0]))
  })

  it('uses a new key when the booking details change', async () => {
    const { result } = renderBooking()
    respond = () => ({ status: 409, data: { success: false, message: 'Overlap' } })

    await act(async () => {
      await expect(result.current.mutateAsync(input)).rejects.toMatchObject({ status: 409 })
    })
    respond = () => ({ status: 201, data: { success: true, message: 'ok', data: { id: 'a2' } } })
    await act(() =>
      result.current.mutateAsync({
        ...input,
        scheduled_start: '2030-01-07T05:00:00.000Z',
        scheduled_end: '2030-01-07T05:15:00.000Z',
      }),
    )

    expect(keyOf(sent[1])).not.toBe(keyOf(sent[0]))
  })

  it('uses a new key for the next booking after one succeeds', async () => {
    const { result } = renderBooking()

    await act(() => result.current.mutateAsync(input))
    await act(() => result.current.mutateAsync(input))

    expect(keyOf(sent[1])).not.toBe(keyOf(sent[0]))
  })
})
