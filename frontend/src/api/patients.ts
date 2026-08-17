import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { Paginated } from '@/api/types'
// import { http } from '@/api/http' // TODO(backend): swap the mock seams below for real calls

export type PatientStatus = 'Outpatient' | 'Admitted' | 'Discharged' | 'Critical'

export interface Patient {
  id: string
  mrn: string
  name: string
  age: number
  gender: 'M' | 'F'
  phone: string
  doctor: string
  department: string
  status: PatientStatus
}

export interface PatientListParams {
  search?: string
  page?: number
  pageSize?: number
}

export interface CreatePatientInput {
  name: string
  age: number
  gender: 'M' | 'F'
  phone: string
  department: string
}

/** Query-key factory — `["patients", ...]` (CLAUDE.md React Query patterns). */
export const patientKeys = {
  all: ['patients'] as const,
  list: (params: PatientListParams) => [...patientKeys.all, 'list', params] as const,
  detail: (id: string) => [...patientKeys.all, 'detail', id] as const,
}

// ---------------------------------------------------------------------------
// TODO(backend): the two functions below are mock seams. When the API is live,
// replace their bodies with the commented `http` calls and delete MOCK_PATIENTS.
// ---------------------------------------------------------------------------

const MOCK_PATIENTS: Patient[] = [
  { id: '1', mrn: 'PT-8291-A', name: 'Ravi Menon', age: 54, gender: 'M', phone: '+91 98847 21908', doctor: 'Dr. A. Chen', department: 'Cardiology', status: 'Admitted' },
  { id: '2', mrn: 'PT-4022-C', name: 'Aisha Khan', age: 32, gender: 'F', phone: '+91 90031 55420', doctor: 'Dr. S. Rao', department: 'Pulmonology', status: 'Outpatient' },
  { id: '3', mrn: 'PT-9188-B', name: 'Thomas George', age: 61, gender: 'M', phone: '+91 99456 12277', doctor: 'Dr. L. Iyer', department: 'Endocrinology', status: 'Critical' },
  { id: '4', mrn: 'PT-1104-D', name: 'Meera Nair', age: 45, gender: 'F', phone: '+91 98120 66431', doctor: 'Dr. P. Verma', department: 'Surgery', status: 'Discharged' },
  { id: '5', mrn: 'PT-6357-F', name: 'David Fernandes', age: 58, gender: 'M', phone: '+91 90876 33019', doctor: 'Dr. A. Chen', department: 'Cardiology', status: 'Outpatient' },
  { id: '6', mrn: 'PT-2048-E', name: 'Sana Sheikh', age: 27, gender: 'F', phone: '+91 97411 20885', doctor: 'Dr. N. Bose', department: 'Neurology', status: 'Outpatient' },
  { id: '7', mrn: 'PT-7791-G', name: 'Karan Malhotra', age: 39, gender: 'M', phone: '+91 98330 77164', doctor: 'Dr. S. Rao', department: 'Pulmonology', status: 'Admitted' },
]

async function fetchPatients(params: PatientListParams): Promise<Paginated<Patient>> {
  // return http.getPaginated<Patient>('/patients', { params })
  await new Promise((r) => setTimeout(r, 300))
  const q = params.search?.trim().toLowerCase()
  const items = q
    ? MOCK_PATIENTS.filter((p) =>
        [p.name, p.mrn, p.phone, p.department].some((f) => f.toLowerCase().includes(q)),
      )
    : MOCK_PATIENTS
  return {
    items,
    pagination: { page: 1, pageSize: items.length || 1, total: items.length, totalPages: 1 },
  }
}

async function createPatient(input: CreatePatientInput): Promise<Patient> {
  // return http.post<Patient>('/patients', input)
  await new Promise((r) => setTimeout(r, 300))
  const n = MOCK_PATIENTS.length + 1
  const created: Patient = {
    id: String(n),
    mrn: `PT-${1000 + n}-X`,
    doctor: 'Unassigned',
    status: 'Outpatient',
    ...input,
  }
  MOCK_PATIENTS.unshift(created)
  return created
}

// ---------------------------------------------------------------------------
// Hooks — the only way components touch patient data (CLAUDE.md).
// ---------------------------------------------------------------------------

export function usePatients(params: PatientListParams = {}) {
  return useQuery({
    queryKey: patientKeys.list(params),
    queryFn: () => fetchPatients(params),
    staleTime: 30_000,
  })
}

export function useCreatePatient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createPatient,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: patientKeys.all })
    },
  })
}
