import { describe, expect, it } from 'vitest'
import { nextDay, offsetMinutesAt, zonedMidnight } from './zonedTime'

describe('zonedMidnight', () => {
  it('uses India’s half-hour offset', () => {
    expect(zonedMidnight('2026-10-20', 'Asia/Kolkata')).toBe('2026-10-20T00:00:00+05:30')
  })

  it('follows a zone across its summer-time change', () => {
    expect(zonedMidnight('2026-01-15', 'Europe/London')).toBe('2026-01-15T00:00:00+00:00')
    expect(zonedMidnight('2026-07-15', 'Europe/London')).toBe('2026-07-15T00:00:00+01:00')
    expect(zonedMidnight('2026-07-15', 'America/New_York')).toBe('2026-07-15T00:00:00-04:00')
  })

  it('names the same instant as midnight on that zone’s clock', () => {
    const iso = zonedMidnight('2026-03-29', 'Europe/London')
    expect(offsetMinutesAt(new Date(iso), 'Europe/London')).toBe(0)
    expect(new Date(iso).toISOString()).toBe('2026-03-29T00:00:00.000Z')
  })
})

describe('nextDay', () => {
  it.each([
    ['2026-10-20', '2026-10-21'],
    ['2026-10-31', '2026-11-01'],
    ['2026-12-31', '2027-01-01'],
    ['2028-02-28', '2028-02-29'],
  ])('%s → %s', (day, next) => {
    expect(nextDay(day)).toBe(next)
  })
})
