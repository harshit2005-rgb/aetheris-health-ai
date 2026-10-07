import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { fail, noContent, ok, serve } from '@/test/fakeApi'
import { cityCare, me, otpRequested, PHONE_MASKED, PHONE_TYPED, verifiedSession } from '@/test/fixtures'
import { loadApp } from '@/test/renderApp'

/**
 * ATTACK: a script injected into the page (or anyone with the device) reads
 * web storage looking for a token, a code or a phone number.
 * OUTCOME: there is nothing to find — the app neither writes nor reads it.
 * (`src/test/setup.ts` also asserts this after every other test, and
 * `src/test/node/storageSource.test.ts` checks the source itself.)
 */
const ROUTER_TRANSITIONS_KEY = 'remix-router-transitions'

describe('web storage', () => {
  it('is never touched across a whole session: load, sign in, use, sign out', async () => {
    const read = vi.spyOn(Storage.prototype, 'getItem')
    const touched = [
      vi.spyOn(Storage.prototype, 'removeItem'),
      vi.spyOn(Storage.prototype, 'clear'),
      vi.spyOn(Storage.prototype, 'key'),
    ]
    serve({
      'POST /auth/refresh': fail(401, 'UNAUTHORIZED'),
      'POST /auth/otp/request': ok(otpRequested(), 202),
      'POST /auth/otp/verify': ok(verifiedSession('access-secret')),
      'GET /me': ok(me([cityCare])),
      'POST /auth/logout': noContent(),
    })
    const { user } = loadApp('/')

    await user.type(await screen.findByLabelText('Mobile number'), PHONE_TYPED)
    await user.click(screen.getByRole('button', { name: 'Send code' }))
    await user.type(await screen.findByLabelText('6-digit code'), '482913')
    await user.click(screen.getByRole('button', { name: 'Verify and continue' }))
    expect(await screen.findByText(PHONE_MASKED)).toBeInTheDocument()

    // Signed in, with a token in memory — and nowhere else.
    expect(window.localStorage).toHaveLength(0)
    expect(window.sessionStorage).toHaveLength(0)
    expect(document.cookie).toBe('')
    expect(window.history.state).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Sign out' }))
    await screen.findByLabelText('Mobile number')

    for (const access of touched) expect(access).not.toHaveBeenCalled()
    // The one read is React Router's own, at start-up: it looks for view
    // transitions it saved before a reload. The app uses none, so the router
    // never writes that key (a write would fail the check in `setup.ts`), and
    // it holds route paths, not data. Nothing else is ever read.
    expect(read.mock.calls).toEqual([[ROUTER_TRANSITIONS_KEY]])
    expect(window.localStorage).toHaveLength(0)
    expect(window.sessionStorage).toHaveLength(0)
  })
})
