import { describe, expect, it } from 'vitest'
import type { DoctorLeave } from '@/api/doctors'
import { formatDayIn } from '@/lib/format'
import { describeLeave, splitLeaves } from './leaveText'

const IST = 'Asia/Kolkata'
const leave = (starts_at: string, ends_at: string, id = 'l1'): DoctorLeave => ({
  id,
  doctor_id: 'doc-1',
  starts_at,
  ends_at,
  reason: null,
})
const day = (iso: string) => formatDayIn(iso, IST)

describe('describeLeave', () => {
  it('reads a whole-day leave as its first and last day, the end being exclusive', () => {
    // 20 to 23 Oct in India, written in UTC as the API returns it.
    const l = leave('2026-10-19T18:30:00Z', '2026-10-23T18:30:00Z')

    expect(describeLeave(l, IST)).toBe(`${day('2026-10-20T00:00:00+05:30')} – ${day('2026-10-23T00:00:00+05:30')}`)
  })

  it('reads a one-day leave as that day', () => {
    expect(describeLeave(leave('2026-10-19T18:30:00Z', '2026-10-20T18:30:00Z'), IST)).toBe(day('2026-10-20T00:00:00+05:30'))
  })

  it('shows the times of a leave that does not start and end at midnight', () => {
    const text = describeLeave(leave('2026-10-20T08:30:00Z', '2026-10-20T11:30:00Z'), IST)
    expect(text).toContain(' – ')
    expect(text).toMatch(/2:00|14:00/)
  })
})

describe('splitLeaves', () => {
  it('keeps leave not yet over as upcoming, earliest first, and the rest as past, latest first', () => {
    const now = new Date('2026-10-21T00:00:00Z').getTime()
    const a = leave('2026-10-01T00:00:00Z', '2026-10-02T00:00:00Z', 'a')
    const b = leave('2026-10-10T00:00:00Z', '2026-10-11T00:00:00Z', 'b')
    const c = leave('2026-10-20T00:00:00Z', '2026-10-22T00:00:00Z', 'c')
    const d = leave('2026-11-01T00:00:00Z', '2026-11-02T00:00:00Z', 'd')

    const { upcoming, past } = splitLeaves([a, b, c, d], now)

    expect(upcoming.map((l) => l.id)).toEqual(['c', 'd'])
    expect(past.map((l) => l.id)).toEqual(['b', 'a'])
  })
})
