import { describe, expect, it } from 'vitest'
import type { WorkingHoursDay } from '@/api/hospitals'
import { daysFromDraft, describeDay, draftErrors, draftFromDays } from './workingHours'

const day = (d: number, open: string | null, close: string | null, is_24h = false): WorkingHoursDay => ({
  day_of_week: d,
  is_24h,
  open_time: open,
  close_time: close,
})

describe('opening hours model', () => {
  it('reads each stored shape and sends all seven days back', () => {
    const stored = [day(0, '09:00:00', '18:00:00'), day(3, null, null, true), day(6, null, null)]

    const draft = draftFromDays(stored)

    expect(draft[0]).toEqual({ mode: 'open', open: '09:00', close: '18:00' })
    expect(draft[3].mode).toBe('all_day')
    expect(draft[6].mode).toBe('closed')
    // Not set yet: a usual clinic day to start from.
    expect(draft[1]).toEqual({ mode: 'open', open: '09:00', close: '18:00' })
    expect(daysFromDraft(draft)).toEqual([
      day(0, '09:00:00', '18:00:00'),
      day(1, '09:00:00', '18:00:00'),
      day(2, '09:00:00', '18:00:00'),
      day(3, null, null, true),
      day(4, '09:00:00', '18:00:00'),
      day(5, '09:00:00', '18:00:00'),
      day(6, null, null),
    ])
  })

  it.each([
    [{ mode: 'open', open: '18:00', close: '09:00' }, 'Closing must be after opening.'],
    [{ mode: 'open', open: '09:00', close: '09:00' }, 'Closing must be after opening.'],
    [{ mode: 'open', open: '', close: '18:00' }, 'Enter an opening and a closing time.'],
  ] as const)('refuses %o', (bad, message) => {
    const draft = draftFromDays([])
    draft[2] = { ...bad }
    expect(draftErrors(draft)).toEqual({ 2: message })
  })

  it('does not check the times of a closed or all-day day', () => {
    const draft = draftFromDays([])
    draft[0] = { mode: 'closed', open: '', close: '' }
    draft[1] = { mode: 'all_day', open: '23:00', close: '01:00' }
    expect(draftErrors(draft)).toEqual({})
  })

  it.each([
    [undefined, 'Not set'],
    [day(0, null, null), 'Closed'],
    [day(0, null, null, true), 'Open 24 hours'],
    [day(0, '08:30:00', '20:00:00'), '08:30–20:00'],
  ])('describes %o as %s', (d, text) => {
    expect(describeDay(d)).toBe(text)
  })
})
