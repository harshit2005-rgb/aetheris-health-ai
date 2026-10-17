import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { InternalAxiosRequestConfig } from 'axios'
import type { Appointment } from '@/api/appointments'
import type { Consultation } from '@/api/consultations'
import { RequirePermission } from '@/components/auth/RequirePermission'
import { signIn, signOut } from '@/test/auth'
import { bodyOf, fail, installFakeApi, ok, paged, type FakeApi, type Outcome } from '@/test/fakeApi'
import ConsultationPage from './ConsultationPage'
import { vitalsProblem } from './vitals'

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))
vi.mock('sonner', () => ({
  toast: { success: toastSuccess, error: toastError },
}))

const DOCTOR = [
  'patient.read',
  'appointment.read',
  'consultation.read',
  'consultation.write',
  'consultation.vitals.record',
  'pharmacy.prescription.read',
  'lab.order.read',
]
const NURSE = ['patient.read', 'appointment.read', 'consultation.read', 'consultation.vitals.record']
const ADMIN = ['patient.read', 'appointment.read', 'consultation.read']

const VISIT: Appointment = {
  id: 'a1',
  hospital_id: 'h1',
  patient_id: 'p1',
  patient_name: 'Ananya Rao',
  doctor_id: 'd1',
  doctor_name: 'Dr. Kiran Reddy',
  scheduled_start: '2026-10-16T04:30:00Z',
  scheduled_end: '2026-10-16T05:00:00Z',
  status: 'in_progress',
  type: 'new',
  reason: null,
  notes: null,
  cancelled_reason: null,
  checked_in_at: null,
  started_at: null,
  completed_at: null,
  created_at: '2026-10-16T04:00:00Z',
  updated_at: '2026-10-16T04:00:00Z',
}

function aNote(extra: Partial<Consultation> = {}): Consultation {
  return {
    id: 'c1',
    appointment_id: 'a1',
    patient_id: 'p1',
    patient_name: 'Ananya Rao',
    patient_mrn: 'MRN-2026-00007',
    doctor_id: 'd1',
    doctor_name: 'Dr. Kiran Reddy',
    status: 'draft',
    visit_at: VISIT.scheduled_start,
    chief_complaint: null,
    diagnoses: [],
    finalized_at: null,
    created_at: '2026-10-16T04:35:00Z',
    updated_at: '2026-10-16T04:35:00Z',
    history: null,
    examination: null,
    plan: null,
    follow_up_date: null,
    vitals: null,
    bmi: null,
    vitals_recorded_at: null,
    vitals_recorded_by: null,
    finalized_by: null,
    is_own: true,
    addenda: [],
    prescriptions: [],
    lab_orders: [],
    ...extra,
  }
}

let note: Consultation | null
let fake: FakeApi
let intercept: (config: InternalAxiosRequestConfig) => Outcome | undefined

function server(config: InternalAxiosRequestConfig): Outcome {
  const url = config.url ?? ''
  const method = config.method ?? 'get'
  if (url === '/appointments/a1' && method === 'get') return ok(VISIT)
  if (url === '/appointments/a1/consultation' && method === 'get')
    return note ? ok(note) : fail(404, 'Consultation not found.')
  if (url === '/prescriptions' || url === '/lab-orders') return paged([])
  if (url === '/consultations' && method === 'post') {
    const body = bodyOf(config) as Partial<Consultation>
    note = aNote({ ...body, diagnoses: body.diagnoses ?? [] })
    return ok(note, 201)
  }
  if (url === '/consultations/c1' && method === 'patch') {
    note = { ...note!, ...(bodyOf(config) as Partial<Consultation>) }
    return ok(note)
  }
  if (url === '/consultations/c1/finalize') {
    if (!note!.chief_complaint || !note!.diagnoses.length)
      return fail(422, 'The note is not complete enough to finalize.', {
        errors: {
          errors: [
            {
              field: 'diagnoses',
              message: 'Add at least one diagnosis first.',
            },
          ],
        },
      })
    note = {
      ...note!,
      status: 'finalized',
      finalized_at: '2026-10-16T05:00:00Z',
    }
    return ok(note)
  }
  if (url === '/appointments/a1/consultation/vitals' && method === 'put') {
    const { vitals } = bodyOf(config) as { vitals: Consultation['vitals'] }
    note = {
      ...(note ?? aNote({ is_own: false })),
      vitals,
      bmi: '22.9',
      vitals_recorded_at: '2026-10-16T04:40:00Z',
    }
    return ok(note)
  }
  if (url === '/consultations/c1/addenda') {
    const { text } = bodyOf(config) as { text: string }
    note = {
      ...note!,
      addenda: [{ id: 'ad1', text, added_by: 'u1', added_at: '2026-10-16T06:00:00Z' }],
    }
    return ok(note, 201)
  }
  return fail(404, `Unhandled ${method} ${url}`)
}

function renderPage(permissions: string[]) {
  signIn(permissions)
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <MemoryRouter initialEntries={['/appointments/a1/consultation']}>
      <QueryClientProvider client={client}>
        <Routes>
          <Route path="/dashboard" element={<p>Dashboard home</p>} />
          <Route
            path="/appointments/:appointmentId/consultation"
            element={
              <RequirePermission permission="consultation.read">
                <ConsultationPage />
              </RequirePermission>
            }
          />
          <Route path="*" element={null} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

const sent = (method: string, url: string) => fake.sent.filter((c) => c.method === method && c.url === url)

beforeEach(() => {
  toastSuccess.mockReset()
  toastError.mockReset()
  note = null
  intercept = () => undefined
  fake = installFakeApi((config) => intercept(config) ?? server(config))
})

afterEach(() => {
  fake.restore()
  signOut()
})

describe('the doctor documents a visit', () => {
  it('starts the note with what was written, then finalizes it', async () => {
    const user = userEvent.setup()
    renderPage(DOCTOR)

    await user.type(await screen.findByLabelText(/Chief complaint/), 'Fever for three days')
    await user.type(screen.getByLabelText('Diagnosis 1'), 'Acute pharyngitis')
    await user.type(screen.getByLabelText('Code'), 'J02.9')
    await user.click(screen.getByRole('button', { name: /Save draft/ }))

    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Draft saved'))
    expect(bodyOf(sent('post', '/consultations')[0])).toMatchObject({
      appointment_id: 'a1',
      chief_complaint: 'Fever for three days',
      diagnoses: [{ code: 'J02.9', description: 'Acute pharyngitis' }],
    })

    await user.click(screen.getByRole('button', { name: /Finalize note/ }))
    await user.click(screen.getByRole('button', { name: 'Finalize' }))

    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Consultation finalized'))
    expect(await screen.findByText('Finalized')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Save draft/ })).not.toBeInTheDocument()
    expect(within(screen.getByRole('list', { name: 'Diagnoses' })).getByText('Acute pharyngitis')).toBeInTheDocument()
  })

  it("shows the server's reason when a note can't be finalized", async () => {
    note = aNote({ chief_complaint: 'Fever' })
    const user = userEvent.setup()
    renderPage(DOCTOR)

    await user.clear(await screen.findByLabelText('Diagnosis 1'))
    await user.click(screen.getByRole('button', { name: /Finalize note/ }))
    await user.click(screen.getByRole('button', { name: 'Finalize' }))

    expect(await screen.findByText('Add at least one diagnosis first.')).toBeInTheDocument()
    expect(note.status).toBe('draft')
  })

  it("tells another doctor they can't write this visit's note", async () => {
    intercept = (c) =>
      c.url === '/consultations' && c.method === 'post'
        ? fail(403, 'Only the doctor seeing this patient can write their consultation note.')
        : undefined
    const user = userEvent.setup()
    renderPage(DOCTOR)

    await user.type(await screen.findByLabelText(/Chief complaint/), 'Fever')
    await user.click(screen.getByRole('button', { name: /Save draft/ }))

    expect(
      await screen.findByText('Only the doctor seeing this patient can write their consultation note.'),
    ).toBeInTheDocument()
  })

  it('adds an addendum to a finalized note', async () => {
    note = aNote({
      status: 'finalized',
      finalized_at: '2026-10-16T05:00:00Z',
      chief_complaint: 'Fever',
      diagnoses: [{ code: null, description: 'Viral fever' }],
    })
    const user = userEvent.setup()
    renderPage(DOCTOR)

    await user.click(await screen.findByRole('button', { name: /Add addendum/ }))
    await user.type(screen.getByLabelText('Addendum'), 'CBC normal.')
    await user.click(screen.getByRole('button', { name: 'Add addendum' }))

    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Addendum added'))
    expect(within(screen.getByRole('list', { name: 'Addenda' })).getByText('CBC normal.')).toBeInTheDocument()
  })
})

describe('vitals', () => {
  it('a nurse records vitals before the doctor has started the note', async () => {
    const user = userEvent.setup()
    renderPage(NURSE)

    await user.click(await screen.findByRole('button', { name: /Record vitals/ }))
    await user.type(screen.getByLabelText('BP systolic (mmHg)'), '128')
    await user.type(screen.getByLabelText('BP diastolic (mmHg)'), '82')
    await user.type(screen.getByLabelText('Weight (kg)'), '70')
    await user.type(screen.getByLabelText('Height (cm)'), '175')
    await user.click(screen.getByRole('button', { name: 'Save vitals' }))

    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Vitals recorded'))
    expect(bodyOf(sent('put', '/appointments/a1/consultation/vitals')[0])).toEqual({
      vitals: {
        bp_systolic: 128,
        bp_diastolic: 82,
        weight_kg: '70',
        height_cm: '175',
      },
    })
    expect(await screen.findByText('128/82 mmHg')).toBeInTheDocument()
    expect(screen.getByText('22.9')).toBeInTheDocument()
    // A nurse gets no note editor.
    expect(screen.queryByLabelText(/Chief complaint/)).not.toBeInTheDocument()
  })

  it.each([
    [{}, 'Enter at least one vital sign.'],
    [{ bp_systolic: '120' }, 'Blood pressure needs both systolic and diastolic.'],
    [{ bp_systolic: '80', bp_diastolic: '90' }, 'Diastolic pressure must be lower than systolic.'],
    [{ spo2: '120' }, 'SpO₂ must be between 50 and 100.'],
  ])('refuses implausible vitals before sending: %o', (partial, message) => {
    const blank = {
      bp_systolic: '',
      bp_diastolic: '',
      pulse: '',
      temperature_c: '',
      spo2: '',
      respiratory_rate: '',
      weight_kg: '',
      height_cm: '',
    }
    expect(vitalsProblem({ ...blank, ...partial })).toBe(message)
  })
})

describe('who sees what', () => {
  it('an admin reads the note but cannot write it', async () => {
    note = aNote({ is_own: false, chief_complaint: 'Fever' })
    renderPage(ADMIN)

    expect(await screen.findByText('Fever')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Save draft/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Record vitals/ })).not.toBeInTheDocument()
  })

  it('says when the doctor has not started yet', async () => {
    renderPage(ADMIN)

    expect(await screen.findByText('The doctor has not started the consultation note yet.')).toBeInTheDocument()
  })

  it('is not shown without consultation.read', async () => {
    renderPage(['appointment.read'])

    await waitFor(() => expect(screen.queryByRole('heading', { name: /Consultation/ })).not.toBeInTheDocument())
  })
})
