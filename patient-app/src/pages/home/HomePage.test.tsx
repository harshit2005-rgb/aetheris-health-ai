import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { usePatientAuthStore } from '@/store/patient-auth-store'
import { fail, ok, okPage, serve, type Outcome } from '@/test/fakeApi'
import { cityCare, lakeside, me, PHONE_E164, PHONE_MASKED } from '@/test/fixtures'
import { renderApp, signIn } from '@/test/renderApp'

const ME = 'GET /me'

describe('home', () => {
  it('shows a loading state while the details are fetched', async () => {
    signIn()
    let answer: (outcome: Outcome) => void = () => {}
    serve({ [ME]: () => new Promise<Outcome>((resolve) => (answer = resolve)) })
    renderApp('/')

    expect(await screen.findByRole('status', { name: 'Loading your details…' })).toBeInTheDocument()

    answer(ok(me()))
    expect(await screen.findByText('No hospital linked yet')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('shows an empty state leading to linking, and leaves the number to the Account page', async () => {
    signIn()
    serve({ [ME]: ok(me()) })
    const { user, router } = renderApp('/')

    expect(await screen.findByText('No hospital linked yet')).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(PHONE_MASKED)
    expect(document.body).not.toHaveTextContent(PHONE_E164)

    await user.click(screen.getByRole('link', { name: 'Link a hospital record' }))

    expect(await screen.findByRole('heading', { name: 'Link your hospital record' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/link-patient')
  })

  it('lists linked hospitals as cards, marking a paused link and saying what to do', async () => {
    signIn()
    serve({ [ME]: ok(me([cityCare, lakeside])), 'GET /appointments': okPage([]) })
    renderApp('/')

    const list = await screen.findByRole('list', { name: 'Your hospitals' })
    const cards = within(list).getAllByRole('listitem')
    expect(cards).toHaveLength(2)

    expect(within(cards[0]).getByText('City Care Hospital')).toBeInTheDocument()
    expect(within(cards[0]).getByText('Linked on 3 Oct 2026')).toBeInTheDocument()
    expect(within(cards[0]).getByText('Linked')).toBeInTheDocument()

    expect(within(cards[1]).getByText('Lakeside Clinic')).toBeInTheDocument()
    expect(within(cards[1]).getByText('Paused')).toBeInTheDocument()
    expect(within(cards[1]).getByText(/contact the hospital/)).toBeInTheDocument()

    expect(screen.queryByText('No hospital linked yet')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Link another hospital' })).toHaveAttribute('href', '/link-patient')
  })

  it('shows an error with a retry that works, without leaking the server’s text', async () => {
    signIn()
    const api = serve({ [ME]: fail(500, 'INTERNAL_ERROR', 'Traceback…') })
    const { user } = renderApp('/')

    expect(await screen.findByRole('alert')).toHaveTextContent('We could not load your details.')
    expect(document.body).not.toHaveTextContent('Traceback')

    api.on({ [ME]: ok(me([cityCare])), 'GET /appointments': okPage([]) })
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('City Care Hospital')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('returns to sign-in with an explanation when the session ends while in use', async () => {
    signIn('access-old')
    const api = serve({ [ME]: fail(401, 'UNAUTHORIZED'), 'POST /auth/refresh': fail(401, 'UNAUTHORIZED') })
    const { router } = renderApp('/')

    expect(await screen.findByText('You have been signed out. Please sign in again.')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(api.calls('POST /auth/refresh')).toHaveLength(1)
    expect(usePatientAuthStore.getState().accessToken).toBeNull()
  })
})
