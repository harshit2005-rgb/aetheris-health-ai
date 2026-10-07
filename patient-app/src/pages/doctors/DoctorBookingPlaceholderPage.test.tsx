import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { doctorDirectory } from '@/test/doctorDirectory'
import { fail, ok, serve, type Routes } from '@/test/fakeApi'
import { ashaRao, cardiology, cityCareHospital, meeraIyer, orthopaedics, vikramShah } from '@/test/fixtures'
import { renderApp, signIn } from '@/test/renderApp'

/**
 * Where "Continue to booking" leads while booking is not in the app: the slot
 * that was chosen, shown back on the hospital's clock, and a plain statement
 * that nothing has been booked. The page sends nothing but the two reads
 * every doctor page makes.
 */

const HOSPITAL = 'GET /hospitals/city-care'
const ASHA = `${HOSPITAL}/doctors/${ashaRao.ref}`
const DOCTORS_PATH = '/hospitals/city-care/doctors'
const ASHA_PATH = `${DOCTORS_PATH}/${ashaRao.ref}`
const BOOK_PATH = `${ASHA_PATH}/book`
const AVAILABILITY_PATH = `${ASHA_PATH}/availability`

const START = '2026-10-09T10:15:00+05:30'
const END = '2026-10-09T10:30:00+05:30'
const q = encodeURIComponent
const SOUND = `date=2026-10-09&start=${q(START)}&end=${q(END)}`

const cityCareWith = (): Routes => ({
  [HOSPITAL]: ok(cityCareHospital),
  ...doctorDirectory('city-care', [ashaRao, meeraIyer, vikramShah], [cardiology, orthopaedics]),
})

function open(query = SOUND) {
  signIn('access-1')
  return renderApp(`${BOOK_PATH}?${query}`)
}

const main = () => screen.getByRole('main')
const title = (name: string) => screen.findByRole('heading', { level: 1, name })
const routeOf = (request: { method?: string; url?: string }) => `${request.method?.toUpperCase()} ${request.url}`

/** A claim that something was booked: "booked", "confirmed", or "reserved" not preceded by "not". */
const CLAIMS_BOOKED = /\b(booked|confirmed|booking confirmed|appointment (is )?(set|made))\b|(?<!not )\breserved\b/i

describe('booking — the placeholder after a slot is chosen', () => {
  it('shows the chosen slot on the hospital’s clock, says nothing is booked, and leads back', async () => {
    const api = serve(cityCareWith())
    open()

    expect(await title('Booking')).toBeInTheDocument()
    expect(screen.getByText('Asha Rao')).toBeInTheDocument()
    expect(screen.getByText('Interventional Cardiology')).toBeInTheDocument()
    expect(screen.getByText('City Care Hospital')).toBeInTheDocument()
    expect(document.title).toBe('Booking · Atheris Health')

    const chosen = screen.getByRole('region', { name: 'Your chosen time' })
    expect(within(chosen).getByText('Day').nextElementSibling).toHaveTextContent(/^Friday 9 October 2026$/)
    expect(within(chosen).getByText('Time').nextElementSibling).toHaveTextContent(/^10:15 – 10:30$/)
    expect(within(chosen).getByText('Times are in the hospital’s local time (Asia/Kolkata)')).toBeInTheDocument()

    expect(screen.getByRole('heading', { level: 2, name: 'Booking is not available in the app yet' })).toBeInTheDocument()
    expect(screen.getByText('This slot is not reserved. For now, please contact the hospital to book an appointment.')).toBeInTheDocument()
    expect(main()).not.toHaveTextContent(CLAIMS_BOOKED)
    expect(screen.queryByText('This booking link is not valid')).not.toBeInTheDocument()

    // Back to the availability as it was left, and to the profile.
    const back = screen.getAllByRole('link', { name: 'Back to availability' })
    expect(back).toHaveLength(2)
    for (const link of back) expect(link).toHaveAttribute('href', `${AVAILABILITY_PATH}?date=2026-10-09&slot=${q(START)}`)
    expect(screen.getByRole('link', { name: 'Back to the profile' })).toHaveAttribute('href', ASHA_PATH)

    // The hospital and the doctor are all that is read; nothing is sent that could book, hold or reserve.
    expect(api.sent.map(routeOf)).toEqual([HOSPITAL, ASHA])
    expect(api.sent.every((request) => (request.method ?? 'get').toLowerCase() === 'get')).toBe(true)
    expect(api.sent.some((request) => /availab|slot|book|appointment|reserv/i.test(request.url ?? ''))).toBe(false)
    expect(main().querySelector('form, input, button:not([data-slot])')).toBeNull()
  })

  it('reads the day by the hospital’s clock: a slot written as UTC falls on the hospital’s next day', async () => {
    serve(cityCareWith())
    // 20:00Z on the 8th is 01:30 on the 9th in Kolkata.
    open(`date=2026-10-09&start=${q('2026-10-08T20:00:00Z')}&end=${q('2026-10-08T20:15:00Z')}`)

    await title('Booking')
    expect(screen.getByText('Friday 9 October 2026')).toBeInTheDocument()
    expect(screen.getByText('01:30 – 01:45')).toBeInTheDocument()
    expect(main()).not.toHaveTextContent(/20:00|20:15|Thursday/)
  })

  it.each([
    ['nothing at all', ''],
    ['no date', `start=${q(START)}&end=${q(END)}`],
    ['a date that is not one', `date=2026-02-30&start=${q(START)}&end=${q(END)}`],
    ['a date with a time', `date=2026-10-09T00:00&start=${q(START)}&end=${q(END)}`],
    ['no start', `date=2026-10-09&end=${q(END)}`],
    ['a start without an offset', `date=2026-10-09&start=${q('2026-10-09T10:15:00')}&end=${q(END)}`],
    ['a start that is not a time', `date=2026-10-09&start=quarter+past+ten&end=${q(END)}`],
    ['a start with its plus left bare', `date=2026-10-09&start=2026-10-09T10:15:00+05:30&end=${q(END)}`],
    ['no end', `date=2026-10-09&start=${q(START)}`],
    ['an end before the start', `date=2026-10-09&start=${q(END)}&end=${q(START)}`],
    ['an end at the start', `date=2026-10-09&start=${q(START)}&end=${q(START)}`],
    ['a start on another day', `date=2026-10-08&start=${q(START)}&end=${q(END)}`],
    ['a start on another day by the hospital’s clock', `date=2026-10-08&start=${q('2026-10-08T20:00:00Z')}&end=${q('2026-10-08T20:15:00Z')}`],
    ['markup in the date', `date=${q('<img src=x onerror=window.pwned=1>')}&start=${q(START)}&end=${q(END)}`],
    ['markup in the start', `date=2026-10-09&start=${q('<script>window.pwned=1</script>')}&end=${q(END)}`],
  ])('a link with %s is not a valid link: nothing of it is shown, and the way back is offered', async (_case, query) => {
    const api = serve(cityCareWith())
    open(query)

    expect(await title('Booking')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'This booking link is not valid' })).toBeInTheDocument()
    expect(screen.getByText('Choose a day and a time from the doctor’s availability to continue.')).toBeInTheDocument()
    expect(screen.queryByText('Your chosen time')).not.toBeInTheDocument()
    expect(screen.queryByText('Booking is not available in the app yet')).not.toBeInTheDocument()
    expect(main()).not.toHaveTextContent(CLAIMS_BOOKED)
    // Nothing from the address is echoed: no date, no time, no markup.
    expect(main()).not.toHaveTextContent(/2026|10:15|10:30|20:00|October|Friday|Thursday|quarter/)
    expect(main().querySelector('script, img, [onerror]')).toBeNull()
    expect((window as { pwned?: unknown }).pwned).toBeUndefined()
    expect(screen.getByRole('link', { name: 'Go to availability' })).toHaveAttribute('href', AVAILABILITY_PATH)
    expect(screen.getByRole('link', { name: 'Back to availability' })).toHaveAttribute('href', AVAILABILITY_PATH)
    expect(screen.getByRole('link', { name: 'Back to the profile' })).toHaveAttribute('href', ASHA_PATH)
    expect(api.sent.map(routeOf)).toEqual([HOSPITAL, ASHA])
  })

  it('a hospital whose zone the browser does not know cannot vouch for the day: the link is not valid', async () => {
    serve({ ...cityCareWith(), [HOSPITAL]: ok({ ...cityCareHospital, timezone: 'Mars/Olympus' }) })
    open()

    expect(await title('Booking')).toBeInTheDocument()
    expect(screen.getByText('This booking link is not valid')).toBeInTheDocument()
    expect(main()).not.toHaveTextContent(/10:15|Friday/)
  })

  it('NOT FOUND — an unknown or hidden doctor is the doctor’s own page, whatever the link says', async () => {
    const api = serve({ ...cityCareWith(), [ASHA]: fail(404, 'RESOURCE_NOT_FOUND', 'server wording') })
    open()

    expect(await title('This doctor is not available')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Browse doctors' })).toHaveAttribute('href', DOCTORS_PATH)
    expect(document.body).not.toHaveTextContent(/server wording|Friday|10:15|Booking/)
    expect(api.sent.map(routeOf)).toEqual([HOSPITAL, ASHA])
  })

  it('ATTACK — a doctor reference that is not one is never sent, whatever the link says', async () => {
    const api = serve({ [HOSPITAL]: ok(cityCareHospital) })
    signIn('access-1')
    renderApp(`${DOCTORS_PATH}/..%2F..%2Fme/book?${SOUND}`)

    expect(await title('This doctor is not available')).toBeInTheDocument()
    expect(api.sent.map(routeOf)).toEqual([HOSPITAL])
  })
})
