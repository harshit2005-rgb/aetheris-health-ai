import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { queryClient } from '@/lib/query-client'
import { fail, headerOf, noContent, ok, serve } from '@/test/fakeApi'
import { cityCare, me, PHONE_E164, PHONE_MASKED } from '@/test/fixtures'
import { isSignedIn, renderApp, signIn } from '@/test/renderApp'

const ME = 'GET /me'
const LOGOUT = 'POST /auth/logout'

describe('account', () => {
  it('shows the masked number from the API, never the full one', async () => {
    signIn()
    serve({ [ME]: ok(me()) })
    renderApp('/account')

    expect(await screen.findByRole('heading', { level: 1, name: 'Account' })).toBeInTheDocument()
    expect(await screen.findByText(PHONE_MASKED)).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(PHONE_E164)
  })

  it('shows an error with a retry that works, without leaking the server’s text', async () => {
    signIn()
    const api = serve({ [ME]: fail(500, 'INTERNAL_ERROR', 'Traceback…') })
    const { user } = renderApp('/account')

    expect(await screen.findByRole('alert')).toHaveTextContent('We could not load your details.')
    expect(document.body).not.toHaveTextContent('Traceback')

    api.on({ [ME]: ok(me()) })
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText(PHONE_MASKED)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('leads to linking a hospital record', async () => {
    signIn()
    serve({ [ME]: ok(me()) })
    const { user, router } = renderApp('/account')

    await user.click(await screen.findByRole('link', { name: 'Link a hospital record' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Link your hospital record' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/link-patient')
  })

  it('is reached from the navigation, which stays on Account while linking a record', async () => {
    signIn()
    serve({ [ME]: ok(me()) })
    const { user } = renderApp('/')
    await screen.findByText('No hospital linked yet')

    const navigation = within(screen.getByRole('navigation', { name: 'Main' }))
    await user.click(navigation.getByRole('link', { name: 'Account' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Account' })).toHaveFocus()
    expect(navigation.getByRole('link', { name: 'Account' })).toHaveAttribute('aria-current', 'page')
    expect(navigation.getByRole('link', { name: 'Home' })).not.toHaveAttribute('aria-current')

    await user.click(screen.getByRole('link', { name: 'Link a hospital record' }))
    await screen.findByRole('heading', { level: 1, name: 'Link your hospital record' })
    expect(navigation.getByRole('link', { name: 'Account' })).toHaveAttribute('aria-current', 'page')
  })

describe('sign out', () => {
  it('revokes the session on the server, forgets it locally and returns to sign-in', async () => {
    signIn('access-1')
    const api = serve({ [ME]: ok(me([cityCare])), [LOGOUT]: noContent() })
    const { user, router } = renderApp('/account')
    await screen.findByText(PHONE_MASKED)

    await user.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(await screen.findByRole('heading', { name: 'Sign in with your mobile number' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')

    const [request] = api.calls(LOGOUT)
    expect(api.calls(LOGOUT)).toHaveLength(1)
    expect(headerOf(request, 'X-Atheris-Patient')).toBe('1')
    expect(request.withCredentials).toBe(true)
    expect(request.data).toBeUndefined()

    expect(isSignedIn()).toBe(false)
    expect(queryClient.getQueryData(['patient', 'me'])).toBeUndefined()
    // Asked-for sign-out: no "you have been signed out" notice.
    expect(screen.queryByText(/You have been signed out/)).not.toBeInTheDocument()
  })

  it('still signs out locally when the server says the session was already gone', async () => {
    signIn()
    const api = serve({ [ME]: ok(me()), [LOGOUT]: fail(401, 'UNAUTHORIZED') })
    const { user } = renderApp('/account')
    await screen.findByText(PHONE_MASKED)

    await user.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(await screen.findByRole('heading', { name: 'Sign in with your mobile number' })).toBeInTheDocument()
    expect(isSignedIn()).toBe(false)
    expect(api.calls('POST /auth/refresh')).toHaveLength(0)
  })

  it('does not pretend to have signed out when the server could not be reached', async () => {
    signIn()
    serve({ [ME]: ok(me()), [LOGOUT]: fail(503, 'SERVICE_UNAVAILABLE') })
    const { user, router } = renderApp('/account')
    await screen.findByText(PHONE_MASKED)

    await user.click(screen.getByRole('button', { name: 'Sign out' }))

    // The refresh cookie is still valid, so a reload would sign back in:
    // the patient is told, and stays where they are.
    expect(await screen.findByRole('alert')).toHaveTextContent('We could not sign you out.')
    expect(router.state.location.pathname).toBe('/account')
    expect(isSignedIn()).toBe(true)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Sign out' })).toBeEnabled())
  })
})
})
