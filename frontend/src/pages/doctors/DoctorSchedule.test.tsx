import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { InternalAxiosRequestConfig } from 'axios'
import type { AvailabilityEntry, AvailabilityWindow, Doctor, DoctorLeave } from '@/api/doctors'
import { signIn, signOut } from '@/test/auth'
import { bodyOf, fail, installFakeApi, ok, type FakeApi, type Outcome } from '@/test/fakeApi'
import DoctorDetailPage from './DoctorDetailPage'

/**
 * A doctor's weekly hours and leave on their page (module spec §5.2, §5.3,
 * §12), against `PUT /doctors/{id}/availability` and `/doctors/{id}/leaves`.
 *
 * The real hooks and Axios instance run against an in-memory server that keeps
 * the schedule the way the API does: a PUT replaces the whole week, and a
 * doctor without `doctor.update` may change only their own schedule.
 */

const { toastSuccess, toastError } = vi.hoisted(() => ({ toastSuccess: vi.fn(), toastError: vi.fn() }))
vi.mock('sonner', () => ({ toast: { success: toastSuccess, error: toastError } }))

// As seeded (backend/app/seeds/seed.py).
const ADMIN = [
  'doctor.read',
  'doctor.update',
  'doctor.delete',
  'doctor.availability.read',
  'doctor.availability.update',
  'doctor.leave.create',
  'doctor.leave.delete',
  'department.read',
]
const DOCTOR = [
  'doctor.read',
  'doctor.availability.read',
  'doctor.availability.update',
  'doctor.leave.create',
  'doctor.leave.delete',
  'department.read',
]
const RECEPTIONIST = ['doctor.read', 'doctor.availability.read', 'department.read']
/** The signed-in user (`src/test/auth.ts`). */
const ME = 'u1'

let api: FakeApi
let doctor: Doctor
let windows: AvailabilityWindow[]
let leaves: DoctorLeave[]
let onWrite: ((config: InternalAxiosRequestConfig) => Outcome | undefined) | null

const makeDoctor = (overrides: Partial<Doctor> = {}): Doctor => ({
  id: 'doc-1',
  hospital_id: 'hosp-1',
  user_id: 'user-9',
  full_name: 'Priya Sharma',
  email: null,
  specialization: 'Cardiology',
  license_number: 'MCI-48213',
  consultation_fee: '950.00',
  department_id: null,
  department_name: null,
  qualifications: [],
  languages: [],
  bio: null,
  status: 'active',
  created_at: '2026-01-05T04:00:00Z',
  updated_at: '2026-09-01T04:00:00Z',
  ...overrides,
})

const win = (day: number, start: string, end: string, duration = 15): AvailabilityWindow => ({
  id: `w-${day}-${start}`,
  day_of_week: day,
  start_time: `${start}:00`,
  end_time: `${end}:00`,
  slot_duration_minutes: duration,
})

/** A doctor without doctor.update may write only their own schedule. */
const mayWrite = () => signedInPermissions.includes('doctor.update') || doctor.user_id === ME
let signedInPermissions: string[] = []

beforeEach(() => {
  toastSuccess.mockReset()
  toastError.mockReset()
  doctor = makeDoctor()
  windows = [win(0, '09:00', '13:00'), win(0, '15:00', '18:00', 20), win(2, '10:00', '12:00', 30)]
  leaves = []
  onWrite = null
  api = installFakeApi((config) => {
    const url = config.url ?? ''
    const method = config.method ?? 'get'
    if (method === 'get') {
      if (url === '/doctors/doc-1') return ok({ ...doctor })
      if (url === '/hospitals/current') return ok({ id: 'hosp-1', name: 'Demo', timezone: 'Asia/Kolkata', currency: 'INR' })
      if (url === '/doctors/doc-1/availability') return ok([...windows])
      if (url === '/doctors/doc-1/leaves') return ok([...leaves])
      return fail(404, 'Not found.')
    }
    const scripted = onWrite?.(config)
    if (scripted) return scripted
    if (!mayWrite()) return fail(403, 'You can change only your own schedule.', { error_code: 'PERMISSION_DENIED' })
    if (url === '/doctors/doc-1/availability' && method === 'put') {
      const { entries } = bodyOf(config) as { entries: AvailabilityEntry[] }
      windows = entries.map((e, i) => ({ id: `saved-${i}`, ...e }))
      return ok([...windows])
    }
    if (url === '/doctors/doc-1/leaves' && method === 'post') {
      const body = bodyOf(config) as { starts_at: string; ends_at: string; reason?: string }
      const leave: DoctorLeave = {
        id: `leave-${leaves.length + 1}`,
        doctor_id: 'doc-1',
        starts_at: new Date(body.starts_at).toISOString(),
        ends_at: new Date(body.ends_at).toISOString(),
        reason: body.reason ?? null,
      }
      leaves.push(leave)
      return ok(leave, 201)
    }
    const deleting = /^\/doctors\/doc-1\/leaves\/(.+)$/.exec(url)
    if (deleting && method === 'delete') {
      leaves = leaves.filter((l) => l.id !== deleting[1])
      return { status: 204, data: '' }
    }
    return fail(404, 'Not found.')
  })
})

afterEach(() => {
  api.restore()
  signOut()
})

function renderPage(permissions: string[]) {
  signedInPermissions = permissions
  signIn(permissions)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <MemoryRouter initialEntries={['/doctors/doc-1']}>
      <QueryClientProvider client={client}>
        <Routes>
          <Route path="/doctors/:doctorId" element={<DoctorDetailPage />} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

const hours = () => screen.findByRole('region', { name: 'Weekly hours' })
const writes = () => api.sent.filter((c) => c.method !== 'get')

describe('weekly hours', () => {
  it('shows each day’s hours to reception, read-only', async () => {
    renderPage(RECEPTIONIST)

    const card = within(await hours())
    expect(await card.findByText('09:00–13:00 (15-min slots), 15:00–18:00 (20-min slots)')).toBeInTheDocument()
    expect(card.getByText('10:00–12:00 (30-min slots)')).toBeInTheDocument()
    expect(card.getAllByText('Off')).toHaveLength(5)
    expect(card.queryByRole('button', { name: /Edit hours/ })).not.toBeInTheDocument()
  })

  it('says when the doctor has no hours, so cannot be booked', async () => {
    windows = []
    renderPage(RECEPTIONIST)

    expect(await within(await hours()).findByText(/No weekly hours set/)).toBeInTheDocument()
  })

  it('lets an admin change a time, add hours and save the whole week', async () => {
    const user = userEvent.setup()
    renderPage(ADMIN)
    const card = within(await hours())
    await user.click(await card.findByRole('button', { name: /Edit hours/ }))

    const mondayFirst = within(card.getByRole('group', { name: 'Monday, hours 1' }))
    fireEvent.change(mondayFirst.getByLabelText('To'), { target: { value: '12:30' } })
    await user.click(card.getByRole('button', { name: 'Add hours on Friday' }))
    await user.click(card.getByRole('button', { name: 'Save hours' }))

    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Schedule saved'))
    const [put] = writes()
    expect(put.method).toBe('put')
    expect(put.url).toBe('/doctors/doc-1/availability')
    expect(bodyOf(put)).toEqual({
      entries: [
        { day_of_week: 0, start_time: '09:00:00', end_time: '12:30:00', slot_duration_minutes: 15 },
        { day_of_week: 0, start_time: '15:00:00', end_time: '18:00:00', slot_duration_minutes: 20 },
        { day_of_week: 2, start_time: '10:00:00', end_time: '12:00:00', slot_duration_minutes: 30 },
        { day_of_week: 4, start_time: '09:00:00', end_time: '13:00:00', slot_duration_minutes: 15 },
      ],
    })
    expect(await card.findByText('09:00–12:30 (15-min slots), 15:00–18:00 (20-min slots)')).toBeInTheDocument()
  })

  it('copies Monday onto Tuesday to Friday', async () => {
    const user = userEvent.setup()
    renderPage(ADMIN)
    const card = within(await hours())
    await user.click(await card.findByRole('button', { name: /Edit hours/ }))

    await user.click(card.getByRole('button', { name: /Copy Monday to Tuesday–Friday/ }))
    await user.click(card.getByRole('button', { name: 'Save hours' }))

    await waitFor(() => expect(writes()).toHaveLength(1))
    const days = (bodyOf(writes()[0]) as { entries: AvailabilityEntry[] }).entries.map((e) => e.day_of_week)
    expect(days).toEqual([0, 0, 1, 1, 2, 2, 3, 3, 4, 4])
  })

  it('refuses overlapping hours on a day without sending anything', async () => {
    const user = userEvent.setup()
    renderPage(ADMIN)
    const card = within(await hours())
    await user.click(await card.findByRole('button', { name: /Edit hours/ }))

    const mondaySecond = within(card.getByRole('group', { name: 'Monday, hours 2' }))
    fireEvent.change(mondaySecond.getByLabelText('From'), { target: { value: '12:00' } })
    await user.click(card.getByRole('button', { name: 'Save hours' }))

    expect(await mondaySecond.findByRole('alert')).toHaveTextContent('Overlaps 09:00–13:00.')
    expect(writes()).toHaveLength(0)
  })

  it('discards the changes on Cancel', async () => {
    const user = userEvent.setup()
    renderPage(ADMIN)
    const card = within(await hours())
    await user.click(await card.findByRole('button', { name: /Edit hours/ }))
    await user.click(card.getByRole('button', { name: /Remove Monday, hours 1/ }))

    await user.click(card.getByRole('button', { name: 'Cancel' }))

    expect(await card.findByText('09:00–13:00 (15-min slots), 15:00–18:00 (20-min slots)')).toBeInTheDocument()
    expect(writes()).toHaveLength(0)
  })

  it('lets a doctor edit their own hours', async () => {
    doctor = makeDoctor({ user_id: ME })
    renderPage(DOCTOR)

    expect(await within(await hours()).findByRole('button', { name: /Edit hours/ })).toBeInTheDocument()
  })

  it('does not offer a doctor a colleague’s hours to edit', async () => {
    renderPage(DOCTOR)
    const card = within(await hours())

    await card.findByText('10:00–12:00 (30-min slots)')
    expect(card.queryByRole('button', { name: /Edit hours/ })).not.toBeInTheDocument()
  })

  it('shows the server’s refusal and keeps the edits', async () => {
    onWrite = () => fail(403, 'You can change only your own schedule.', { error_code: 'PERMISSION_DENIED' })
    const user = userEvent.setup()
    renderPage(ADMIN)
    const card = within(await hours())
    await user.click(await card.findByRole('button', { name: /Edit hours/ }))

    await user.click(card.getByRole('button', { name: 'Save hours' }))

    expect(await card.findByText('You can change only your own schedule.')).toBeInTheDocument()
    expect(card.getByRole('button', { name: 'Save hours' })).toBeInTheDocument()
  })
})

describe('leave', () => {
  const leaveCard = () => screen.findByRole('region', { name: 'Leave' })

  it('adds whole days of leave at midnight on the hospital’s clock, the last day included', async () => {
    const user = userEvent.setup()
    renderPage(ADMIN)
    const card = within(await leaveCard())
    await user.click(await card.findByRole('button', { name: /Add leave/ }))
    const dialog = within(await screen.findByRole('dialog'))

    fireEvent.change(dialog.getByLabelText(/First day/), { target: { value: '2026-10-20' } })
    fireEvent.change(dialog.getByLabelText(/Last day/), { target: { value: '2026-10-22' } })
    await user.type(dialog.getByLabelText(/Reason/), 'Conference')
    await user.click(dialog.getByRole('button', { name: 'Add leave' }))

    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Leave added'))
    const [post] = writes()
    expect(post.url).toBe('/doctors/doc-1/leaves')
    expect(bodyOf(post)).toEqual({
      starts_at: '2026-10-20T00:00:00+05:30',
      ends_at: '2026-10-23T00:00:00+05:30',
      reason: 'Conference',
    })
  })

  it('refuses a last day before the first', async () => {
    const user = userEvent.setup()
    renderPage(ADMIN)
    const card = within(await leaveCard())
    await user.click(await card.findByRole('button', { name: /Add leave/ }))
    const dialog = within(await screen.findByRole('dialog'))

    fireEvent.change(dialog.getByLabelText(/First day/), { target: { value: '2026-10-22' } })
    fireEvent.change(dialog.getByLabelText(/Last day/), { target: { value: '2026-10-20' } })
    await user.click(dialog.getByRole('button', { name: 'Add leave' }))

    expect(await dialog.findByText('The last day must be on or after the first')).toBeInTheDocument()
    expect(writes()).toHaveLength(0)
  })

  it('cancels a leave after asking', async () => {
    leaves = [
      {
        id: 'leave-9',
        doctor_id: 'doc-1',
        starts_at: '2099-01-04T18:30:00Z',
        ends_at: '2099-01-06T18:30:00Z',
        reason: 'Family',
      },
    ]
    const user = userEvent.setup()
    renderPage(ADMIN)
    const card = within(await leaveCard())
    expect(await card.findByText('Family')).toBeInTheDocument()

    await user.click(card.getByRole('button', { name: /Cancel leave/ }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Cancel leave' }))

    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Leave cancelled'))
    expect(writes().map((c) => [c.method, c.url])).toEqual([['delete', '/doctors/doc-1/leaves/leave-9']])
    expect(await card.findByText('No upcoming leave.')).toBeInTheDocument()
  })

  it('shows leave to reception without the controls', async () => {
    leaves = [
      { id: 'leave-9', doctor_id: 'doc-1', starts_at: '2099-01-04T18:30:00Z', ends_at: '2099-01-06T18:30:00Z', reason: 'Family' },
    ]
    renderPage(RECEPTIONIST)
    const card = within(await leaveCard())

    expect(await card.findByText('Family')).toBeInTheDocument()
    expect(card.queryByRole('button', { name: /Add leave/ })).not.toBeInTheDocument()
    expect(card.queryByRole('button', { name: /Cancel leave/ })).not.toBeInTheDocument()
  })
})
