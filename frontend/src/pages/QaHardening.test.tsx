import { describe, it, expect, afterEach, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Detail, InfoCard } from '@/components/ui/detail-card'
import DashboardLayout from '@/layouts/DashboardLayout'
import { signIn, signOut } from '@/test/auth'
import { installFakeApi, ok, paged, type FakeApi } from '@/test/fakeApi'
import PatientsPage from './patients/PatientsPage'

/** Fixes from the final demo QA pass, each held in place by a test. */

let fake: FakeApi

beforeEach(() => {
  fake = installFakeApi((config) =>
    config.url === '/notifications/unread-count' ? ok({ unread: 0 }) : paged([]),
  )
})

afterEach(() => {
  fake.restore()
  signOut()
})

function renderIn(page: React.ReactNode, permissions: string[], shell = false) {
  signIn(permissions)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <MemoryRouter initialEntries={['/patients']}>
      <QueryClientProvider client={client}>
        <Routes>
          <Route element={shell ? <DashboardLayout /> : undefined}>
            <Route path="/patients" element={page} />
          </Route>
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('detail cards', () => {
  it('let a long unbroken value wrap instead of widening the page', () => {
    // A doctor's email overflowed its column and scrolled the page sideways.
    render(
      <InfoCard title="Practice">
        <Detail label="Email" value="a.very.long.address@demohospital.example.com" />
      </InfoCard>,
    )

    const value = screen.getByText('a.very.long.address@demohospital.example.com')
    expect(value).toHaveClass('[overflow-wrap:anywhere]')
    // The grid column must be allowed to shrink below the value's width.
    expect(value.parentElement).toHaveClass('min-w-0')
  })
})

describe('patient search', () => {
  it('explains how search matches when a full name finds nothing', async () => {
    // The API matches the start of a first or last name, or a whole MRN or
    // phone number — "Ravi Menon" as one term matches no one.
    const user = userEvent.setup()
    renderIn(<PatientsPage />, ['patient.read', 'patient.create'])

    await user.type(await screen.findByLabelText('Search name, MRN or phone…'), 'Ravi Menon')

    expect(await screen.findByText('No matching patients')).toBeInTheDocument()
    expect(screen.getByText(/a full name will not match/)).toBeInTheDocument()
    expect(screen.getByText(/MRN or phone number must be entered in full/)).toBeInTheDocument()
  })

  it('offers Register on an empty registry only to those who may register', async () => {
    renderIn(<PatientsPage />, ['patient.read'])

    const empty = (await screen.findByText('No patients yet')).closest('div') as HTMLElement
    expect(screen.getByText('Patients registered at this hospital will appear here.')).toBeInTheDocument()
    expect(within(empty).queryByRole('button', { name: /Register/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Register Patient/ })).not.toBeInTheDocument()
  })

  it('still offers Register on an empty registry to a user with patient.create', async () => {
    renderIn(<PatientsPage />, ['patient.read', 'patient.create'])

    await screen.findByText('No patients yet')
    expect(screen.getByText('Register your first patient to start building the registry.')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Register Patient/ }).length).toBeGreaterThan(0)
  })
})

describe('top bar', () => {
  it('names the search box that is not available yet, and keeps it disabled', async () => {
    renderIn(<p>Page body</p>, ['patient.read'], true)
    await screen.findByText('Page body')

    const search = screen.getByRole('textbox', { name: 'Global search (coming soon)' })
    expect(search).toBeDisabled()
  })
})
