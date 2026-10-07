import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { deferred, fail, headerOf, ok, serve, unreachable } from '@/test/fakeApi'
import { cityCareHospital } from '@/test/fixtures'
import { renderApp, signIn } from '@/test/renderApp'

const HOSPITAL = 'GET /hospitals/city-care'

function open(path = '/hospitals/city-care/doctors') {
  signIn('access-1')
  return renderApp(path)
}

const title = (name: string) => screen.findByRole('heading', { level: 1, name })

/** Anything that would read as a doctor, a count of them, or a way to book one. */
const DOCTOR_DATA = /\bDr\.?\s|\bMBBS\b|\bMD\b|speciali[sz]|cardiolog|\d+\s+doctors?\b|years? of experience|available today|book now|consultation fee/i

/**
 * `/hospitals/:hospitalRef/doctors` is where "View Doctors" leads. Doctor
 * discovery does not exist yet, so the page must say exactly that — and show
 * nothing that could be taken for a doctor.
 */
describe('doctor discovery — the entry point', () => {
  it('names the hospital from the API and says plainly that there is no doctor list yet', async () => {
    const api = serve({ [HOSPITAL]: ok(cityCareHospital) })
    open()

    expect(await title('Doctors at City Care Hospital')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'Doctor listings are not available yet' })).toBeInTheDocument()
    expect(
      screen.getByText(
        'You cannot browse or book the doctors at this hospital in the app yet. For now, please contact the hospital directly.',
      ),
    ).toBeInTheDocument()

    // Two ways back, both to the hospital.
    expect(screen.getByRole('link', { name: 'Back to City Care Hospital' })).toHaveAttribute('href', '/hospitals/city-care')
    expect(screen.getByRole('link', { name: 'Back to the hospital' })).toHaveAttribute('href', '/hospitals/city-care')
    expect(document.title).toBe('Doctors · Atheris Health')

    // The hospital is the only thing asked for: there is no doctor endpoint to call, and none is called.
    expect(api.sent.map((request) => `${request.method?.toUpperCase()} ${request.url}`)).toEqual([HOSPITAL])
    expect(headerOf(api.sent[0], 'Authorization')).toBe('Bearer access-1')
  })

  it('NO FAKE DATA — shows no doctor, count, specialty, card or placeholder for one, loading or loaded', async () => {
    const { handler, answer } = deferred()
    serve({ [HOSPITAL]: handler })
    open()

    // While loading: a placeholder for the page header and nothing else.
    expect(await screen.findByRole('status', { name: 'Loading hospital…' })).toBeInTheDocument()
    const main = screen.getByRole('main')
    expect(main.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(2)
    expect(within(main).queryByRole('list')).not.toBeInTheDocument()
    expect(within(main).queryByRole('listitem')).not.toBeInTheDocument()

    answer(ok(cityCareHospital))
    await title('Doctors at City Care Hospital')

    expect(main.querySelector('[data-slot="skeleton"]')).toBeNull()
    for (const role of ['list', 'listitem', 'table', 'img', 'article', 'searchbox', 'combobox', 'button']) {
      expect(within(main).queryByRole(role)).not.toBeInTheDocument()
    }
    expect(main).not.toHaveTextContent(DOCTOR_DATA)
    expect(main).not.toHaveTextContent(/\d/)
    // No promise of a date either.
    expect(main).not.toHaveTextContent(/coming soon|soon|next week|launch/i)
    // Every link on the page leads back to the hospital.
    expect(within(main).getAllByRole('link').map((link) => link.getAttribute('href'))).toEqual([
      '/hospitals/city-care',
      '/hospitals/city-care',
    ])
  })

  it('NOT FOUND — an unknown or unavailable hospital has no doctors page either', async () => {
    serve({ [HOSPITAL]: fail(404, 'RESOURCE_NOT_FOUND', 'server wording that must not be shown') })
    open()

    expect(await title('This hospital is not available')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Browse hospitals' })).toHaveAttribute('href', '/hospitals')
    expect(screen.queryByText('Doctor listings are not available yet')).not.toBeInTheDocument()
    expect(document.body).not.toHaveTextContent('server wording')
  })

  it('ERROR and OFFLINE — says which, and retries', async () => {
    const api = serve({ [HOSPITAL]: unreachable })
    const { user } = open()

    expect(await screen.findByRole('alert')).toHaveTextContent('No connection')

    api.on({ [HOSPITAL]: fail(500, 'INTERNAL_ERROR', 'Traceback…') })
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('We could not load this hospital. Please try again.')).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent('Traceback')
    expect(screen.queryByText('Doctor listings are not available yet')).not.toBeInTheDocument()

    api.on({ [HOSPITAL]: ok(cityCareHospital) })
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await title('Doctors at City Care Hospital')).toBeInTheDocument()
  })
})
