import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { Paginated } from '@/api/types'
import type { PatientSummary } from '@/api/patients'
import PatientsPage from './PatientsPage'

// Mock at the module boundary (frontend/CLAUDE.md): the page sees hooks, not axios.
const usePatientsMock = vi.fn()
vi.mock('@/api/patients', () => ({
  usePatients: (params: unknown) => usePatientsMock(params),
  useCreatePatient: () => ({ mutateAsync: vi.fn(), isPending: false }),
  patientKeys: { all: ['patients'] },
}))

function result(overrides: Record<string, unknown>) {
  return {
    data: undefined,
    isPending: false,
    isLoading: false,
    isError: false,
    isFetching: false,
    refetch: vi.fn(),
    ...overrides,
  }
}

const page = (items: PatientSummary[], total = items.length): Paginated<PatientSummary> => ({
  items,
  pagination: { page: 1, pageSize: 25, total, totalPages: Math.max(1, Math.ceil(total / 25)) },
})

const ravi: PatientSummary = {
  id: 'p1',
  mrn: 'PT-8291-A',
  first_name: 'Ravi',
  last_name: 'Menon',
  full_name: 'Ravi Menon',
  date_of_birth: '1971-05-02',
  age: 54,
  gender: 'male',
  phone: '+919884721908',
  status: 'active',
}

function renderPage() {
  return render(
    <MemoryRouter>
      <PatientsPage />
    </MemoryRouter>,
  )
}

describe('PatientsPage', () => {
  beforeEach(() => usePatientsMock.mockReset())

  it('renders patient rows from the API response', () => {
    usePatientsMock.mockReturnValue(result({ data: page([ravi]) }))
    renderPage()
    expect(screen.getByText('Ravi Menon')).toBeInTheDocument()
    expect(screen.getByText('PT-8291-A')).toBeInTheDocument()
    expect(screen.getByText('active')).toBeInTheDocument()
  })

  it('shows the empty state when there are no patients', () => {
    usePatientsMock.mockReturnValue(result({ data: page([], 0) }))
    renderPage()
    expect(screen.getByText('No patients yet')).toBeInTheDocument()
  })

  it('shows an error state with a retry action', () => {
    usePatientsMock.mockReturnValue(result({ isError: true }))
    renderPage()
    expect(screen.getByText("Couldn't load patients")).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
