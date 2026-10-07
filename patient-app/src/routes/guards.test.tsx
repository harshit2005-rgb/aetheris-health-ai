import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ok, serve } from '@/test/fakeApi'
import { me } from '@/test/fixtures'
import { renderApp, signIn } from '@/test/renderApp'

const LOGIN_HEADING = 'Sign in with your mobile number'

describe('route guards', () => {
  it.each([
    '/',
    '/link-patient',
    '/hospitals',
    '/hospitals?q=care&city=Bengaluru&page=2',
    '/hospitals/city-care',
    '/hospitals/city-care/doctors',
    '/no-such-page',
  ])('sends a visitor at %s to the sign-in page', async (path) => {
    const api = serve({})
    const { router } = renderApp(path)

    expect(await screen.findByRole('heading', { name: LOGIN_HEADING })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    // Nothing protected is requested for a visitor.
    expect(api.sent).toHaveLength(0)
  })

  it.each(['/login', '/verify-otp', '/no-such-page'])('sends a signed-in patient at %s home', async (path) => {
    signIn()
    serve({ 'GET /me': ok(me()) })
    const { router } = renderApp(path)

    expect(await screen.findByRole('heading', { name: 'Welcome' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
  })

  it('offers no staff route', async () => {
    signIn()
    serve({ 'GET /me': ok(me()) })
    const { router } = renderApp('/dashboard/patients')

    expect(await screen.findByRole('heading', { name: 'Welcome' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
  })
})
