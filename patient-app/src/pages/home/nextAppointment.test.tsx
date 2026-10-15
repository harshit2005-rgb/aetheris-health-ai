import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fail, ok, okPage, serve } from '@/test/fakeApi'
import { cityCare, me } from '@/test/fixtures'
import { anAppointment, manyAppointments, myAppointmentRef, myAppointmentsEndpoints } from '@/test/myAppointments'
import { renderApp, signIn } from '@/test/renderApp'

const ME = 'GET /me'

describe('home — next appointment', () => {
  it('shows the first upcoming appointment the server gives, and only that one', async () => {
    signIn()
    const mine = myAppointmentsEndpoints(manyAppointments(3))
    serve({ [ME]: ok(me([cityCare])), ...mine.routes })
    renderApp('/')

    const list = await screen.findByRole('list', { name: 'Next appointment' })
    const cards = within(list).getAllByRole('listitem')
    expect(cards).toHaveLength(1)
    expect(within(cards[0]).getByRole('heading', { level: 3, name: 'Doctor 01' })).toBeInTheDocument()
    expect(within(cards[0]).getByText('Monday 12 October 2026')).toBeInTheDocument()
    expect(within(cards[0]).getByRole('link', { name: /^View appointment Doctor 01/ })).toHaveAttribute(
      'href',
      `/appointments/${myAppointmentRef(100)}`,
    )
    // Cancelling is for the appointment's own page, never from home.
    expect(within(cards[0]).queryByRole('link', { name: /^Cancel/ })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'All my appointments' })).toHaveAttribute('href', '/appointments')
  })

  it('asks for the first page of upcoming appointments and nothing else', async () => {
    signIn()
    const mine = myAppointmentsEndpoints([anAppointment()])
    const api = serve({ [ME]: ok(me([cityCare])), ...mine.routes })
    renderApp('/')

    await screen.findByRole('heading', { level: 3, name: 'Asha Menon' })
    const [request] = api.calls('GET /appointments')
    expect(api.calls('GET /appointments')).toHaveLength(1)
    expect(request.params).toMatchObject({ scope: 'upcoming', page: 1 })
  })

  it('says when nothing is coming up, with the ways to book and to past visits', async () => {
    signIn()
    serve({ [ME]: ok(me([cityCare])), 'GET /appointments': okPage([]) })
    renderApp('/')

    expect(await screen.findByText('No upcoming appointments')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Find a doctor' })).toHaveAttribute('href', '/hospitals')
    expect(screen.getByRole('link', { name: 'My appointments' })).toHaveAttribute('href', '/appointments')
  })

  it('fails on its own with a retry that works, leaving the rest of home in place', async () => {
    signIn()
    const api = serve({ [ME]: ok(me([cityCare])), 'GET /appointments': fail(500, 'INTERNAL_ERROR', 'Traceback…') })
    const { user } = renderApp('/')

    expect(await screen.findByRole('alert')).toHaveTextContent('We could not load your next appointment.')
    expect(document.body).not.toHaveTextContent('Traceback')
    expect(screen.getByText('City Care Hospital')).toBeInTheDocument()

    api.on({ 'GET /appointments': okPage([]) })
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('No upcoming appointments')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('is not asked for until a hospital is linked: appointments come only through one', async () => {
    signIn()
    const api = serve({ [ME]: ok(me()) })
    renderApp('/')

    await screen.findByText('No hospital linked yet')
    expect(screen.queryByRole('heading', { name: 'Next appointment' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'My appointments' })).toHaveAttribute('href', '/appointments')
    expect(api.calls('GET /appointments')).toHaveLength(0)
  })
})
