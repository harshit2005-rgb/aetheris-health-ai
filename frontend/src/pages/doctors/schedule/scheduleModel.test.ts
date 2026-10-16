import { describe, expect, it } from 'vitest'
import type { AvailabilityWindow } from '@/api/doctors'
import { copyDay, entriesFromWeek, newWindow, slotCount, weekErrors, weekFromWindows, type DraftWeek } from './scheduleModel'

const window = (day: number, start: string, end: string, duration = 15): AvailabilityWindow => ({
  id: `${day}-${start}`,
  day_of_week: day,
  start_time: `${start}:00`,
  end_time: `${end}:00`,
  slot_duration_minutes: duration,
})

const week = (...days: [number, string, string, number?][]): DraftWeek =>
  weekFromWindows(days.map(([d, s, e, m]) => window(d, s, e, m)))

describe('the editable week', () => {
  it('puts each window on its day, in time order, and sends it back as the API takes it', () => {
    const windows = [window(0, '15:00', '18:00', 20), window(0, '09:00', '13:00'), window(4, '10:00', '12:00', 30)]

    const draft = weekFromWindows(windows)

    expect(draft).toHaveLength(7)
    expect(draft[0].map((w) => `${w.start}-${w.end}`)).toEqual(['09:00-13:00', '15:00-18:00'])
    expect(draft[1]).toEqual([])
    expect(entriesFromWeek(draft)).toEqual([
      { day_of_week: 0, start_time: '09:00:00', end_time: '13:00:00', slot_duration_minutes: 15 },
      { day_of_week: 0, start_time: '15:00:00', end_time: '18:00:00', slot_duration_minutes: 20 },
      { day_of_week: 4, start_time: '10:00:00', end_time: '12:00:00', slot_duration_minutes: 30 },
    ])
  })

  it('an empty week is a schedule with no hours', () => {
    expect(entriesFromWeek(weekFromWindows([]))).toEqual([])
  })
})

describe('the rules the server applies', () => {
  it('accepts windows that only touch: that is how a slot length changes mid-day', () => {
    expect(weekErrors(week([0, '09:00', '11:00', 15], [0, '11:00', '13:00', 30]))).toEqual({})
  })

  it('refuses an overlap on the same day, naming the window it overlaps', () => {
    const draft = week([2, '09:00', '12:00'], [2, '11:30', '13:00'])

    const errors = weekErrors(draft)

    expect(errors[draft[2][1].key]).toBe('Overlaps 09:00–12:00.')
    expect(errors[draft[2][0].key]).toBeUndefined()
  })

  it('allows the same hours on different days', () => {
    expect(weekErrors(week([0, '09:00', '12:00'], [1, '09:00', '12:00']))).toEqual({})
  })

  it.each([
    ['12:00', '12:00', 15, 'The end must be after the start.'],
    ['13:00', '09:00', 15, 'The end must be after the start.'],
    ['', '09:00', 15, 'Enter a start and an end time.'],
    ['09:00', '12:00', 25, 'Choose a slot length.'],
  ])('refuses %s–%s with %d-minute slots', (start, end, duration, message) => {
    const draft: DraftWeek = [[{ key: 'x', start, end, duration }], [], [], [], [], [], []]
    expect(weekErrors(draft)).toEqual({ x: message })
  })
})

describe('editing helpers', () => {
  it('copies Monday onto the weekdays, replacing what they had and leaving the weekend', () => {
    const draft = week([0, '09:00', '13:00'], [2, '14:00', '16:00'], [5, '10:00', '12:00'])

    const copied = copyDay(draft, 0, [1, 2, 3, 4])

    for (const day of [1, 2, 3, 4]) expect(copied[day].map((w) => `${w.start}-${w.end}`)).toEqual(['09:00-13:00'])
    expect(copied[5].map((w) => `${w.start}-${w.end}`)).toEqual(['10:00-12:00'])
    // Each copy is its own window, editable on its own.
    expect(new Set(copied.flat().map((w) => w.key)).size).toBe(copied.flat().length)
  })

  it('starts a new window after the day’s last one, or as a morning clinic', () => {
    expect(newWindow([])).toMatchObject({ start: '09:00', end: '13:00', duration: 15 })
    const [day] = week([0, '09:00', '13:00', 20])
    expect(newWindow(day)).toMatchObject({ start: '13:00', end: '15:00', duration: 20 })
  })

  it.each([
    [{ start: '09:00', end: '13:00', duration: 15 }, 16],
    [{ start: '09:00', end: '09:50', duration: 20 }, 2],
    [{ start: '09:00', end: '09:10', duration: 15 }, 0],
    [{ start: '13:00', end: '09:00', duration: 15 }, 0],
  ])('counts whole slots: %o → %d', (w, count) => {
    expect(slotCount(w)).toBe(count)
  })
})
