import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { http } from '@/api/http'
import type { Paginated } from '@/api/types'

/**
 * Patient module API — typed hooks over the real backend contract
 * (`backend/app/api/v1/patients.py`, `backend/app/schemas/patient.py`).
 * Components use these hooks only; they never call the axios client directly.
 */

export type Gender = 'male' | 'female' | 'other' | 'unspecified'
export type PatientStatus = 'active' | 'inactive'
export type BloodGroup = 'A+' | 'A-' | 'B+' | 'B-' | 'AB+' | 'AB-' | 'O+' | 'O-'

/** Compact shape returned by the list/search endpoint (`PatientSummaryResponse`). */
export interface PatientSummary {
  id: string
  mrn: string
  first_name: string
  last_name: string
  full_name: string
  date_of_birth: string
  age: number
  gender: Gender
  phone: string | null
  status: PatientStatus
}

/** Full record returned by get/create/update (`PatientResponse`). */
export interface Patient extends PatientSummary {
  hospital_id: string
  blood_group: string | null
  email: string | null
  address: Record<string, unknown> | null
  emergency_contact: Record<string, unknown> | null
  marital_status: string | null
  occupation: string | null
  allergies: Array<Record<string, unknown>>
  chronic_conditions: Array<Record<string, unknown>>
  current_medications: Array<Record<string, unknown>>
  notes: string | null
  created_at: string
  updated_at: string
}

/** Query parameters accepted by `GET /patients` (snake_case, as the backend expects). */
export interface PatientListParams {
  q?: string
  gender?: Gender
  page?: number
  page_size?: number
  include_inactive?: boolean
}

/** Body for `POST /patients` (`CreatePatientRequest`). MRN is generated server-side. */
export interface CreatePatientInput {
  first_name: string
  last_name: string
  date_of_birth: string
  gender: Gender
  blood_group?: BloodGroup
  phone?: string
  email?: string
}

/** Query-key factory — `["patients", ...]` (frontend/CLAUDE.md React Query patterns). */
export const patientKeys = {
  all: ['patients'] as const,
  list: (params: PatientListParams) => [...patientKeys.all, 'list', params] as const,
  detail: (id: string) => [...patientKeys.all, 'detail', id] as const,
}

/** List / search patients. Backends supports `q`, `gender`, `include_inactive`, and page/size. */
export function usePatients(params: PatientListParams = {}) {
  return useQuery<Paginated<PatientSummary>>({
    queryKey: patientKeys.list(params),
    queryFn: () => http.getPaginated<PatientSummary>('/patients', { params }),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  })
}

/** Fetch one patient's full record (Patient Profile view). */
export function usePatient(id: string | undefined) {
  return useQuery<Patient>({
    queryKey: patientKeys.detail(id ?? ''),
    queryFn: () => http.get<Patient>(`/patients/${id}`),
    enabled: !!id,
  })
}

/** Register a patient, then refresh every patient list. */
export function useCreatePatient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: CreatePatientInput) => http.post<Patient>('/patients', input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: patientKeys.all })
    },
  })
}
