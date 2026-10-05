import { useRef } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { http } from '@/api/http'
import { doctorKeys } from '@/api/doctors'
import { newIdempotencyKey } from '@/api/idempotency'
import { ApiError, type Paginated, type ListQueryOptions } from '@/api/types'

/**
 * Appointment module API — typed hooks over the real backend contract
 * (`backend/app/api/v1/appointments.py`, `backend/app/schemas/appointment.py`).
 */

export type AppointmentStatus =
  | 'booked'
  | 'checked_in'
  | 'in_progress'
  | 'completed'
  | 'cancelled'
  | 'no_show'

export type AppointmentType = 'new' | 'follow_up' | 'walk_in' | 'emergency'

/** Compact shape from the list endpoint (`AppointmentSummaryResponse`). */
export interface AppointmentSummary {
  id: string
  patient_id: string
  patient_name: string
  doctor_id: string
  doctor_name: string
  scheduled_start: string
  scheduled_end: string
  status: AppointmentStatus
  type: AppointmentType
}

/** Full record from get/book (`AppointmentResponse`). */
export interface Appointment extends AppointmentSummary {
  hospital_id: string
  reason: string | null
  notes: string | null
  cancelled_reason: string | null
  checked_in_at: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

/** Body for `POST /appointments` (`BookAppointmentRequest`). Timestamps are tz-aware ISO. */
export interface BookAppointmentInput {
  patient_id: string
  doctor_id: string
  scheduled_start: string
  scheduled_end: string
  type: AppointmentType
  reason?: string
  notes?: string
}

export interface AppointmentListParams {
  patient_id?: string
  doctor_id?: string
  /**
   * Calendar day (YYYY-MM-DD). The server interprets it in the hospital's own
   * timezone, so no offset is sent — a client can only express whole hours,
   * which is wrong for India (UTC+5:30).
   */
  appointment_date?: string
  appointment_status?: AppointmentStatus
  appointment_type?: AppointmentType
  page?: number
  page_size?: number
}

export const appointmentKeys = {
  all: ['appointments'] as const,
  list: (params: AppointmentListParams) => [...appointmentKeys.all, 'list', params] as const,
  detail: (id: string) => [...appointmentKeys.all, 'detail', id] as const,
}

/**
 * Translate the hook's parameter names into the query names the API reads.
 *
 * The server's filters are `date`, `status` and `type`
 * (docs/18-API_CONTRACTS.md §5.3). It ignores unknown query parameters, so
 * sending `appointment_date` or `appointment_status` does not fail — it
 * silently returns every appointment, unfiltered.
 */
export function toAppointmentQuery(params: AppointmentListParams): Record<string, unknown> {
  const { appointment_date, appointment_status, appointment_type, ...rest } = params
  return { ...rest, date: appointment_date, status: appointment_status, type: appointment_type }
}

/** List appointments. For the day queue, pass `appointment_date`. */
export function useAppointments(
  params: AppointmentListParams = {},
  options: ListQueryOptions = {},
) {
  return useQuery<Paginated<AppointmentSummary>>({
    enabled: options.enabled ?? true,
    queryKey: appointmentKeys.list(params),
    queryFn: () =>
      http.getPaginated<AppointmentSummary>('/appointments', {
        params: toAppointmentQuery(params),
      }),
    staleTime: 15_000,
    placeholderData: keepPreviousData,
  })
}

/** One appointment's full record. Pass `enabled: false` for users without `appointment.read`. */
export function useAppointment(id: string, options: ListQueryOptions = {}) {
  return useQuery<Appointment>({
    enabled: (options.enabled ?? true) && !!id,
    queryKey: appointmentKeys.detail(id),
    queryFn: () => http.get<Appointment>(`/appointments/${id}`),
    staleTime: 15_000,
  })
}

/** The lifecycle endpoints that take no body: `POST /appointments/{id}/{action}`. */
export type AppointmentTransition = 'check-in' | 'start' | 'complete'

/**
 * The server rejected a lifecycle call because the appointment is not in the
 * state this screen showed (moved on, gone, or changed by someone else). The
 * lists are stale, so they are refetched even though the call failed.
 */
function isStaleAppointment(err: unknown): boolean {
  return err instanceof ApiError && [400, 404, 409].includes(err.status ?? 0)
}

/**
 * Check in, start or complete an appointment (docs/18-API_CONTRACTS.md §5.4).
 *
 * The state machine lives on the server: an illegal move is a 400. The mutation
 * settles only after the appointment lists have refetched, so `isPending`
 * covers the whole window in which a row still shows its old status.
 */
export function useAppointmentTransition() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: AppointmentTransition }) =>
      http.post<Appointment>(`/appointments/${id}/${action}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: appointmentKeys.all }),
    onError: (err) => {
      if (isStaleAppointment(err)) qc.invalidateQueries({ queryKey: appointmentKeys.all })
    },
  })
}

/** Cancel an appointment. The API requires a reason (module spec §11). */
export function useCancelAppointment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      http.post<Appointment>(`/appointments/${id}/cancel`, { reason }),
    onSuccess: () => {
      // A cancelled appointment gives its slot back.
      qc.invalidateQueries({ queryKey: doctorKeys.slots() })
      return qc.invalidateQueries({ queryKey: appointmentKeys.all })
    },
    onError: (err) => {
      if (isStaleAppointment(err)) qc.invalidateQueries({ queryKey: appointmentKeys.all })
    },
  })
}

/**
 * Book an appointment, then refresh the queue. Throws ApiError (409 on doctor overlap).
 *
 * `POST /appointments` requires an `Idempotency-Key` (docs/18-API_CONTRACTS.md
 * §5.2). The key belongs to one logical booking: resubmitting the same details
 * after a timeout or a dropped connection reuses it, so the server replays the
 * original appointment (200) instead of booking twice. Changed details are a
 * different booking and get a new key — the server answers a known key with the
 * appointment it already holds, whatever the new body says.
 */
export function useBookAppointment() {
  const qc = useQueryClient()
  const attempt = useRef<{ fingerprint: string; key: string } | null>(null)
  return useMutation({
    mutationFn: (input: BookAppointmentInput) => {
      const fingerprint = JSON.stringify(input)
      if (attempt.current?.fingerprint !== fingerprint) {
        attempt.current = { fingerprint, key: newIdempotencyKey() }
      }
      return http.post<Appointment>('/appointments', input, {
        headers: { 'Idempotency-Key': attempt.current.key },
      })
    },
    onSuccess: () => {
      // Booked: the next submission is a new booking even if the details match.
      attempt.current = null
      qc.invalidateQueries({ queryKey: appointmentKeys.all })
      qc.invalidateQueries({ queryKey: doctorKeys.slots() })
    },
    onError: (err) => {
      // 409: another desk took the slot. The slots on screen are out of date.
      if (err instanceof ApiError && err.status === 409) {
        qc.invalidateQueries({ queryKey: doctorKeys.slots() })
      }
    },
  })
}
