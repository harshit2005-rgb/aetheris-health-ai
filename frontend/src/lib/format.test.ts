import { describe, it, expect } from 'vitest'
import { formatDate, formatRelativeTime } from './format'

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
