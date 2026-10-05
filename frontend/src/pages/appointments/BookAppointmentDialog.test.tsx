import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios'
import { api } from '@/lib/api'
import type { AppointmentSummary } from '@/api/appointments'
import { BookAppointmentDialog } from './BookAppointmentDialog'
import AppointmentsPage from './AppointmentsPage'

/**
 * The booking request itself is never mocked here: the real `useBookAppointment`
 * hook, `http` wrapper and Axios instance run, and only the network adapter is
 * replaced. Mocking the hook is how the missing `Idempotency-Key` (a 422 from
 * the real API) went unnoticed.
 */

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock('sonner', () => ({ toast: { success: toastSuccess, error: toastError } }))
// The pickers only read; their data is fixed so the form can be filled in.
vi.mock('@/api/doctors', () => ({
  useDoctors: () => ({
    data: { items: [{ id: 'doc-1', full_name: 'Dr. Anita Chen', specialization: 'Cardiology' }] },
  }),
}))
vi.mock('@/api/patients', () => ({
  usePatients: ({ q }: { q?: string }) => ({
    data: { items: q ? [{ id: 'pat-1', full_name: 'Ravi Menon', mrn: 'MRN-2026-00042' }] : [] },
  }),
}))
vi.mock('@/hooks/usePermissions', () => ({
  usePermissions: () => ({ can: () => true, canAny: () => true, nav: [], role: undefined }),
}))

type Outcome = { status: number; data: unknown }
type Handler = (config: InternalAxiosRequestConfig) => Outcome | Promise<Outcome>

const originalAdapter = api.defaults.adapter
let sent: InternalAxiosRequestConfig[]
let onPost: Handler
let onGet: Handler

const ok = (data: unknown, status = 200): Outcome => ({
  status,
  data: { success: true, message: 'ok', data },
})

const listOf = (items: AppointmentSummary[]): Outcome => ({
  status: 200,
  data: {
    success: true,
    message: 'ok',
    data: items,
    metadata: {
      pagination: { page: 1, page_size: 25, total_records: items.length, total_pages: 1 },
    },
  },
})

const booked: AppointmentSummary = {
  id: 'appt-1',
  patient_id: 'pat-1',
  patient_name: 'Ravi Menon',
  doctor_id: 'doc-1',
  doctor_name: 'Dr. Anita Chen',
  scheduled_start: '2030-01-07T04:00:00Z',
  scheduled_end: '2030-01-07T04:15:00Z',
  status: 'booked',
  type: 'new',
}

const posts = () => sent.filter((c) => c.method === 'post')
const keyOf = (config: InternalAxiosRequestConfig) => config.headers.get('Idempotency-Key')

beforeEach(() => {
  sent = []
  toastSuccess.mockReset()
  toastError.mockReset()
  onPost = () => ok(booked, 201)
  onGet = () => listOf([])
  const adapter: AxiosAdapter = async (config) => {
    sent.push(config)
    const outcome = await (config.method === 'post' ? onPost(config) : onGet(config))
    const response = { ...outcome, statusText: '', headers: {}, config }
    if (outcome.status >= 400) {
      throw new AxiosError('Request failed', 'ERR_BAD_REQUEST', config, null, response)
    }
    return response
  }
  api.defaults.adapter = adapter
})

afterEach(() => {
  api.defaults.adapter = originalAdapter
})

function withClient(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </MemoryRouter>,
  )
}

function renderDialog() {
  return withClient(<BookAppointmentDialog trigger={<button type="button">Open booking</button>} />)
}

/** Fill every required field the way reception would, leaving the dialog ready to submit. */
async function fillForm(user: ReturnType<typeof userEvent.setup>, time = '09:30') {
  await screen.findByRole('dialog')
  await user.type(screen.getByLabelText(/Patient/), 'Ravi')
  await user.click(await screen.findByRole('button', { name: /Ravi Menon/ }))
  await user.click(screen.getByRole('combobox', { name: /Doctor/ }))
  await user.click(await screen.findByRole('option', { name: /Dr\. Anita Chen/ }))
  await user.type(screen.getByLabelText(/Date/), '2030-01-07')
  await user.type(screen.getByLabelText(/Time/), time)
}

async function openAndFill(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Open booking' }))
  await fillForm(user)
}

const submit = (user: ReturnType<typeof userEvent.setup>) =>
  user.click(screen.getByRole('button', { name: /^Book$/ }))

describe('BookAppointmentDialog', () => {
  it('opens and blocks submit with validation errors when required fields are empty', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: 'Open booking' }))
    // Dialog is open with the form.
    expect(screen.getByText('Book appointment')).toBeInTheDocument()

    // Submit empty -> zod validation surfaces required-field errors.
    await submit(user)
    expect(await screen.findByText('Choose a patient')).toBeInTheDocument()
    expect(screen.getByText('Choose a doctor')).toBeInTheDocument()
    expect(screen.getByText('Pick a date')).toBeInTheDocument()
    expect(screen.getByText('Pick a time')).toBeInTheDocument()
    expect(posts()).toHaveLength(0)
  })

  it('books with the body and Idempotency-Key the API requires, then closes', async () => {
    const user = userEvent.setup()
    renderDialog()
    await openAndFill(user)
    await user.type(screen.getByLabelText(/Reason/), 'Persistent cough')

    await submit(user)

    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Appointment booked'))
    expect(posts()).toHaveLength(1)
    const [request] = posts()
    expect(`${request.baseURL}${request.url}`).toBe('/api/v1/appointments')
    expect(request.headers.get('Content-Type')).toBe('application/json')

    const key = keyOf(request)
    expect(typeof key).toBe('string')
    expect((key as string).length).toBeGreaterThanOrEqual(8)
    expect((key as string).length).toBeLessThanOrEqual(200)

    // Reception's local wall-clock time, sent as a tz-aware instant.
    const start = new Date('2030-01-07T09:30')
    expect(JSON.parse(request.data as string)).toEqual({
      patient_id: 'pat-1',
      doctor_id: 'doc-1',
      scheduled_start: start.toISOString(),
      scheduled_end: new Date(start.getTime() + 15 * 60_000).toISOString(),
      type: 'new',
      reason: 'Persistent cough',
    })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('treats an idempotent replay (200) as the same success', async () => {
    onPost = () => ok(booked, 200)
    const user = userEvent.setup()
    renderDialog()
    await openAndFill(user)

    await submit(user)

    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Appointment booked'))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('sends one request and shows progress while a booking is in flight', async () => {
    let finish: (outcome: Outcome) => void = () => {}
    onPost = () => new Promise<Outcome>((resolve) => (finish = resolve))
    const user = userEvent.setup()
    renderDialog()
    await openAndFill(user)

    // Two submits in the same tick, before React can disable the button.
    const form = screen.getByRole('dialog').querySelector('form') as HTMLFormElement
    fireEvent.submit(form)
    fireEvent.submit(form)

    const busy = await screen.findByRole('button', { name: /Booking/ })
    expect(busy).toBeDisabled()
    expect(busy).toHaveAttribute('aria-busy', 'true')
    await user.click(busy)
    expect(posts()).toHaveLength(1)

    finish(ok(booked, 201))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledTimes(1))
    expect(posts()).toHaveLength(1)
  })

  it('retries a failed booking with the same Idempotency-Key', async () => {
    onPost = () => ({ status: 503, data: { success: false, message: 'Service unavailable.' } })
    const user = userEvent.setup()
    renderDialog()
    await openAndFill(user)

    await submit(user)
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('Service unavailable.'))
    // The dialog stays open with the details intact, ready to retry.
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    onPost = () => ok(booked, 200)
    await submit(user)
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled())

    expect(posts()).toHaveLength(2)
    expect(keyOf(posts()[1])).toBe(keyOf(posts()[0]))
  })

  it('shows API validation errors on the form', async () => {
    onPost = () => ({
      status: 422,
      data: {
        success: false,
        message: 'Validation failed.',
        error_code: 'VALIDATION_ERROR',
        errors: [
          { field: 'scheduled_start', message: 'scheduled_start must include a UTC offset.' },
          { field: '', message: 'Duration must be one of [10, 15, 20, 30, 45, 60] minutes.' },
        ],
      },
    })
    const user = userEvent.setup()
    renderDialog()
    await openAndFill(user)

    await submit(user)

    expect(await screen.findByText('scheduled_start must include a UTC offset.')).toBeInTheDocument()
    expect(
      screen.getByText('Duration must be one of [10, 15, 20, 30, 45, 60] minutes.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(toastSuccess).not.toHaveBeenCalled()
  })

  it('explains a double-booking conflict (409)', async () => {
    onPost = () => ({ status: 409, data: { success: false, message: 'Overlap.' } })
    const user = userEvent.setup()
    renderDialog()
    await openAndFill(user)

    await submit(user)

    expect(await screen.findByText('Time unavailable')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('shows a business-rule rejection (400) from the API', async () => {
    onPost = () => ({
      status: 400,
      data: { success: false, message: 'The doctor is not available at that time.' },
    })
    const user = userEvent.setup()
    renderDialog()
    await openAndFill(user)

    await submit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The doctor is not available at that time.',
    )
  })

  it('rejects a reason longer than the API allows without sending it', async () => {
    const user = userEvent.setup()
    renderDialog()
    await openAndFill(user)
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: 'x'.repeat(501) } })

    await submit(user)

    expect(await screen.findByText('Keep the reason under 500 characters')).toBeInTheDocument()
    expect(posts()).toHaveLength(0)
  })
})

describe('AppointmentsPage booking', () => {
  it('shows the new appointment in the queue after booking', async () => {
    // The queue is empty until the booking is accepted.
    let created = false
    onGet = () => listOf(created ? [booked] : [])
    onPost = () => {
      created = true
      return ok(booked, 201)
    }
    const user = userEvent.setup()
    withClient(<AppointmentsPage />)
    expect(await screen.findByText('No appointments today')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^Book$/ }))
    await fillForm(user)
    await user.click(screen.getAllByRole('button', { name: /^Book$/ }).at(-1) as HTMLElement)

    expect(await screen.findByRole('cell', { name: 'Ravi Menon' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Dr. Anita Chen' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
