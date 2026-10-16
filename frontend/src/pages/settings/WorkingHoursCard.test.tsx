import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { WorkingHoursDay } from '@/api/hospitals'
import { signIn, signOut } from '@/test/auth'
import { bodyOf, fail, installFakeApi, ok, type FakeApi } from '@/test/fakeApi'
import { WorkingHoursCard } from './WorkingHoursCard'

/** The opening-hours card against `GET`/`PUT /hospitals/current/working-hours`. */

const { toastSuccess } = vi.hoisted(() => ({ toastSuccess: vi.fn() }))
vi.mock('sonner', () => ({ toast: { success: toastSuccess, error: vi.fn() } }))

let api: FakeApi
let stored: WorkingHoursDay[]

beforeEach(() => {
  toastSuccess.mockReset()
  stored = [
    { day_of_week: 0, is_24h: false, open_time: '09:00:00', close_time: '18:00:00' },
    { day_of_week: 6, is_24h: false, open_time: null, close_time: null },
  ]
  api = installFakeApi((config) => {
    if (config.url !== '/hospitals/current/working-hours') return fail(404, 'Not found.')
    if (config.method === 'put') {
      stored = (bodyOf(config) as { days: WorkingHoursDay[] }).days
      return ok([...stored])
    }
    return ok([...stored])
  })
})

afterEach(() => {
  api.restore()
  signOut()
})

function renderCard(permissions: string[]) {
  signIn(permissions)
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <WorkingHoursCard />
    </QueryClientProvider>,
  )
}

const card = async () => within(await screen.findByRole('region', { name: /Working hours/ }))

describe('working hours', () => {
  it('shows each day, with days not yet set saying so, read-only without settings.update', async () => {
    renderCard(['settings.read'])
    const c = await card()

    expect(await c.findByText('09:00–18:00')).toBeInTheDocument()
    expect(c.getByText('Closed')).toBeInTheDocument()
    expect(c.getAllByText('Not set')).toHaveLength(5)
    expect(c.queryByRole('button', { name: /Edit hours/ })).not.toBeInTheDocument()
  })

  it('saves all seven days, with a changed time and a closed day', async () => {
    const user = userEvent.setup()
    renderCard(['settings.read', 'settings.update'])
    const c = await card()
    await user.click(await c.findByRole('button', { name: /Edit hours/ }))

    fireEvent.change(c.getByLabelText('Monday closes'), { target: { value: '20:00' } })
    await user.click(c.getByRole('combobox', { name: 'Tuesday status' }))
    await user.click(await screen.findByRole('option', { name: 'Closed' }))
    await user.click(c.getByRole('button', { name: 'Save hours' }))

    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Working hours saved'))
    const put = api.sent.find((s) => s.method === 'put')
    const days = (bodyOf(put!) as { days: WorkingHoursDay[] }).days
    expect(days).toHaveLength(7)
    expect(days[0]).toEqual({ day_of_week: 0, is_24h: false, open_time: '09:00:00', close_time: '20:00:00' })
    expect(days[1]).toEqual({ day_of_week: 1, is_24h: false, open_time: null, close_time: null })
    expect(days[6]).toEqual({ day_of_week: 6, is_24h: false, open_time: null, close_time: null })
    expect(await c.findByText('09:00–20:00')).toBeInTheDocument()
  })

  it('refuses closing before opening without sending anything', async () => {
    const user = userEvent.setup()
    renderCard(['settings.read', 'settings.update'])
    const c = await card()
    await user.click(await c.findByRole('button', { name: /Edit hours/ }))

    fireEvent.change(c.getByLabelText('Monday closes'), { target: { value: '08:00' } })
    await user.click(c.getByRole('button', { name: 'Save hours' }))

    expect(await within(c.getByRole('group', { name: 'Monday' })).findByRole('alert')).toHaveTextContent(
      'Closing must be after opening.',
    )
    expect(api.sent.filter((s) => s.method === 'put')).toHaveLength(0)
  })
})
