import { SLOT_DURATIONS, type AvailabilityEntry, type AvailabilityWindow } from '@/api/doctors'

/**
 * The weekly availability editor's model, kept apart from React so its rules
 * can be tested on their own. The rules are the server's (module spec §11,
 * `SetAvailabilityRequest`), so what passes here is what the API accepts.
 */

/** 0 = Monday … 6 = Sunday, as the API numbers them. */
export const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'] as const

/** One window being edited. Times are `HH:MM`, hospital wall-clock. */
export interface DraftWindow {
  /** Stable React key; not sent. */
  key: string
  start: string
  end: string
  duration: number
}

/** Seven days, Monday first, each with its windows. */
export type DraftWeek = DraftWindow[][]

let nextKey = 0
const newKey = () => `w${(nextKey += 1)}`

/** `09:00:00` → `09:00`. */
const hhmm = (time: string) => time.slice(0, 5)

/** The saved windows as an editable week, each day in time order. */
export function weekFromWindows(windows: AvailabilityWindow[]): DraftWeek {
  const week: DraftWeek = DAY_NAMES.map(() => [])
  for (const w of windows) {
    if (w.day_of_week < 0 || w.day_of_week > 6) continue
    week[w.day_of_week].push({
      key: newKey(),
      start: hhmm(w.start_time),
      end: hhmm(w.end_time),
      duration: w.slot_duration_minutes,
    })
  }
  for (const day of week) day.sort((a, b) => a.start.localeCompare(b.start))
  return week
}

/** The week as the API's `entries`, `HH:MM:00`. */
export function entriesFromWeek(week: DraftWeek): AvailabilityEntry[] {
  return week.flatMap((day, dayOfWeek) =>
    day.map((w) => ({
      day_of_week: dayOfWeek,
      start_time: `${w.start}:00`,
      end_time: `${w.end}:00`,
      slot_duration_minutes: w.duration,
    })),
  )
}

/** A new window for a day: after the day's last one, else a morning clinic. */
export function newWindow(day: DraftWindow[]): DraftWindow {
  const last = [...day].sort((a, b) => a.start.localeCompare(b.start)).at(-1)
  if (last && last.end < '23:00') {
    const [h, m] = last.end.split(':').map(Number)
    const endHour = Math.min(h + 2, 23)
    return { key: newKey(), start: last.end, end: `${String(endHour).padStart(2, '0')}:${String(m).padStart(2, '0')}`, duration: last.duration }
  }
  return { key: newKey(), start: '09:00', end: '13:00', duration: 15 }
}

/** `from`'s windows copied onto each of `to`, replacing what those days had. */
export function copyDay(week: DraftWeek, from: number, to: number[]): DraftWeek {
  return week.map((day, index) =>
    to.includes(index) && index !== from ? week[from].map((w) => ({ ...w, key: newKey() })) : day,
  )
}

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/

/**
 * What is wrong with each window, keyed by `DraftWindow.key`. Empty when the
 * week can be saved. Windows that touch (one ending as the next starts) are
 * fine: that is how a mid-day change of slot length is written.
 */
export function weekErrors(week: DraftWeek): Record<string, string> {
  const errors: Record<string, string> = {}
  week.forEach((day) => {
    for (const w of day) {
      if (!TIME.test(w.start) || !TIME.test(w.end)) errors[w.key] = 'Enter a start and an end time.'
      else if (w.start >= w.end) errors[w.key] = 'The end must be after the start.'
      else if (!(SLOT_DURATIONS as readonly number[]).includes(w.duration)) errors[w.key] = 'Choose a slot length.'
    }
    const valid = day.filter((w) => !errors[w.key]).sort((a, b) => a.start.localeCompare(b.start))
    for (let i = 1; i < valid.length; i += 1) {
      if (valid[i].start < valid[i - 1].end) {
        errors[valid[i].key] = `Overlaps ${valid[i - 1].start}–${valid[i - 1].end}.`
      }
    }
  })
  return errors
}

/** How many slots a window makes: whole slots only, as the server generates them. */
export function slotCount(w: Pick<DraftWindow, 'start' | 'end' | 'duration'>): number {
  if (!TIME.test(w.start) || !TIME.test(w.end) || w.duration <= 0) return 0
  const minutes = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5))
  return Math.max(0, Math.floor((minutes(w.end) - minutes(w.start)) / w.duration))
}
