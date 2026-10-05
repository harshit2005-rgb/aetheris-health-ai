import { describe, it, expect, afterEach, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import DashboardLayout from '@/layouts/DashboardLayout'
import { signIn, signOut } from '@/test/auth'
import { installFakeApi, ok, paged, type FakeApi } from '@/test/fakeApi'
import LandingPage from './LandingPage'
import PricingPage from './PricingPage'
import PatientsPage from './patients/PatientsPage'

/**
 * The backend has no AI provider connected and no AI endpoint an assistant
 * could call, so the frontend must not offer one or describe one as working.
 * These tests hold the shell and the public pages to that.
 */

/** Wording that would describe an AI capability as something the product does today. */
const AI_CLAIMS = [
  /copilot/i,
  /ask aetheris/i,
  /how can i help/i,
  /context-aware/i,
  /summari[sz]e patient/i,
  /AI-assisted/i,
  /high-risk patients/i,
  /revenue summary/i,
  /the AI (reads|flags|reviews)/i,
  /agentic/i,
  /AI agent/i,
  /AI tools/i,
]

function expectNoAiClaims() {
  const text = document.body.textContent ?? ''
  for (const claim of AI_CLAIMS) expect(text).not.toMatch(claim)
}

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

function renderShell(permissions: string[], page = <p>Page body</p>) {
  signIn(permissions)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <MemoryRouter initialEntries={['/patients']}>
      <QueryClientProvider client={client}>
        <Routes>
          <Route element={<DashboardLayout />}>
            <Route path="/patients" element={page} />
          </Route>
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('the signed-in shell', () => {
  it('says AI assistance is not available, and does not offer it as a control', async () => {
    renderShell(['patient.read'])
    await screen.findByText('Page body')

    const notice = screen.getByRole('note', { name: 'AI assistance is not yet available' })
    expect(within(notice).getByText('AI assistance')).toBeInTheDocument()
    expect(within(notice).getByText('Not yet available')).toBeInTheDocument()
    // A notice, not something to click: nothing inside it is interactive.
    expect(within(notice).queryByRole('button')).not.toBeInTheDocument()
    expect(within(notice).queryByRole('link')).not.toBeInTheDocument()
    expect(notice.closest('button, a')).toBeNull()
  })

  it('has no assistant launcher, prompt, composer or send button anywhere', async () => {
    renderShell(['patient.read'])
    await screen.findByText('Page body')

    expect(screen.queryByRole('button', { name: /copilot|assistant|\bAI\b/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^send$/i })).not.toBeInTheDocument()
    expect(screen.queryByPlaceholderText(/ask/i)).not.toBeInTheDocument()
    for (const prompt of [
      "Show today's appointments",
      'Summarize patient history',
      'List high-risk patients',
      'Generate revenue summary',
      'Find pending invoices',
    ]) {
      expect(screen.queryByText(prompt)).not.toBeInTheDocument()
    }
    expectNoAiClaims()
  })

  it('opens no assistant when the notice is clicked, and calls no AI endpoint', async () => {
    const user = userEvent.setup()
    renderShell(['patient.read'])
    await screen.findByText('Page body')

    await user.click(screen.getByRole('note', { name: 'AI assistance is not yet available' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(fake.sent.some((c) => /\/ai\b|recommend/.test(c.url ?? ''))).toBe(false)
  })

  it('keeps the rest of the shell working: navigation still follows permissions', async () => {
    renderShell(['patient.read', 'appointment.read', 'notification.read.own'])
    await screen.findByText('Page body')

    // The desktop rail (the breadcrumbs are a navigation landmark too).
    const nav = screen.getByRole('complementary')
    expect(within(nav).getByRole('link', { name: /Patients/ })).toHaveAttribute('href', '/patients')
    expect(within(nav).getByRole('link', { name: /Appointments/ })).toBeInTheDocument()
    expect(within(nav).queryByRole('link', { name: /Billing/ })).not.toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /^Notifications/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
  })
})

describe('the Patients page', () => {
  it('describes the registry without claiming AI summaries or admissions', async () => {
    renderShell(['patient.read'], <PatientsPage />)

    expect(await screen.findByRole('heading', { name: 'Patients' })).toBeInTheDocument()
    expect(screen.getByText(/The patient registry/)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/admissions/i)
    expectNoAiClaims()
  })
})

describe('the public pages', () => {
  function renderPublic(page: React.ReactNode) {
    render(<MemoryRouter>{page}</MemoryRouter>)
  }

  it('landing: says AI is planned, not present', () => {
    renderPublic(<LandingPage />)

    expectNoAiClaims()
    expect(screen.getByRole('heading', { name: 'AI assistance — planned' })).toBeInTheDocument()
    expect(screen.getByText(/Not part of the product today/)).toBeInTheDocument()
    expect(screen.getByText('Does Aetheris include AI features today?')).toBeInTheDocument()
    expect(screen.queryByText(/intelligent platform/i)).not.toBeInTheDocument()
  })

  it('pricing: sells no AI features', () => {
    renderPublic(<PricingPage />)

    expectNoAiClaims()
    expect(screen.getByRole('heading', { name: 'Plans for every hospital' })).toBeInTheDocument()
    // The only "AI" left is the company's name.
    const text = (document.body.textContent ?? '').replace(/Aetheris Health AI/g, '')
    expect(text).not.toMatch(/\bAI\b/)
  })
})
