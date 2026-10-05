import { describe, it, expect } from 'vitest'
import { formatDate, formatRelativeTime, formatDayIn, formatTimeIn, isoDateIn } from './format'

describe('formatRelativeTime', () => {
  const now = Date.parse('2026-10-05T12:00:00Z')
  const ago = (ms: number) => new Date(now - ms).toISOString()
  // Compared with Intl's own output so the test holds in any locale.
  const relative = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
  const MINUTE = 60_000
  const HOUR = 60 * MINUTE
  const DAY = 24 * HOUR

  it('treats the last few seconds as now', () => {
    expect(formatRelativeTime(ago(10_000), now)).toBe(relative.format(0, 'second'))
  })

  it('counts minutes, then hours, then days', () => {
    expect(formatRelativeTime(ago(5 * MINUTE), now)).toBe(relative.format(-5, 'minute'))
    expect(formatRelativeTime(ago(3 * HOUR), now)).toBe(relative.format(-3, 'hour'))
    expect(formatRelativeTime(ago(DAY), now)).toBe(relative.format(-1, 'day'))
    expect(formatRelativeTime(ago(6 * DAY), now)).toBe(relative.format(-6, 'day'))
  })

  it('falls back to a date once it is more than a week old', () => {
    const iso = ago(30 * DAY)
    expect(formatRelativeTime(iso, now)).toBe(formatDate(iso))
  })

  it('echoes a value it cannot parse', () => {
    expect(formatRelativeTime('not a date', now)).toBe('not a date')
  })
})

describe('hospital-clock helpers', () => {
  // 20:00 UTC on 6 Oct is already 01:30 on 7 Oct in Asia/Kolkata.
  const lateEvening = '2026-10-06T20:00:00Z'

  it('isoDateIn gives the calendar day in the named zone', () => {
    expect(isoDateIn(lateEvening, 'Asia/Kolkata')).toBe('2026-10-07')
    expect(isoDateIn(lateEvening, 'UTC')).toBe('2026-10-06')
    expect(isoDateIn(lateEvening, 'America/Los_Angeles')).toBe('2026-10-06')
  })

  it('isoDateIn falls back to the viewer for an unknown zone, and is empty for a bad date', () => {
    expect(isoDateIn(lateEvening, 'Not/AZone')).toMatch(/^2026-10-0[67]$/)
    expect(isoDateIn('not a date', 'UTC')).toBe('')
  })

  it('formatDayIn names the day in the named zone', () => {
    expect(formatDayIn(lateEvening, 'Asia/Kolkata')).toMatch(/Wed.*7/)
    expect(formatDayIn(lateEvening, 'UTC')).toMatch(/Tue.*6/)
    expect(formatDayIn('not a date', 'UTC')).toBe('not a date')
  })

  it('formatTimeIn uses the named zone, or the viewer without one', () => {
    expect(formatTimeIn(lateEvening, 'Asia/Kolkata')).toMatch(/1:30/)
    expect(formatTimeIn(lateEvening)).toBe(formatTimeIn(lateEvening, undefined))
  })
})
