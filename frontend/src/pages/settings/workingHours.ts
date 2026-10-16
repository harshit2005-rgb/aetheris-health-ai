import type { WorkingHoursDay } from '@/api/hospitals'

/**
 * The opening-hours editor's model, apart from React. The rules are the
 * server's (module 14 §11, `WorkingHoursDay`), so what passes here is what
 * the API accepts.
 */

export const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'] as const

export type DayMode = 'closed' | 'open' | 'all_day'

/** One day being edited. Times are `HH:MM`, hospital wall-clock. */
export interface DraftDay {
  mode: DayMode
  open: string
  close: string
}

/** A day not set yet opens as a usual clinic day, so the form starts somewhere sensible. */
const DEFAULT_OPEN: DraftDay = { mode: 'open', open: '09:00', close: '18:00' }

/** The stored week as seven editable days, Monday first. A day with no entry is a default open day. */
export function draftFromDays(days: WorkingHoursDay[]): DraftDay[] {
  return DAY_NAMES.map((_, index) => {
    const day = days.find((d) => d.day_of_week === index)
    if (!day) return { ...DEFAULT_OPEN }
    if (day.is_24h) return { mode: 'all_day', open: DEFAULT_OPEN.open, close: DEFAULT_OPEN.close }
    if (!day.open_time || !day.close_time) return { mode: 'closed', open: DEFAULT_OPEN.open, close: DEFAULT_OPEN.close }
    return { mode: 'open', open: day.open_time.slice(0, 5), close: day.close_time.slice(0, 5) }
  })
}

/** The seven days as the API takes them: every day sent, so none is left "not set". */
export function daysFromDraft(draft: DraftDay[]): WorkingHoursDay[] {
  return draft.map((day, index) => ({
    day_of_week: index,
    is_24h: day.mode === 'all_day',
    open_time: day.mode === 'open' ? `${day.open}:00` : null,
    close_time: day.mode === 'open' ? `${day.close}:00` : null,
  }))
}

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/

/** What is wrong with each day, by index. Empty when the week can be saved. */
export function draftErrors(draft: DraftDay[]): Record<number, string> {
  const errors: Record<number, string> = {}
  draft.forEach((day, index) => {
    if (day.mode !== 'open') return
    if (!TIME.test(day.open) || !TIME.test(day.close)) errors[index] = 'Enter an opening and a closing time.'
    else if (day.close <= day.open) errors[index] = 'Closing must be after opening.'
  })
  return errors
}

/** A day in words for the read-only view. */
export function describeDay(day: WorkingHoursDay | undefined): string {
  if (!day) return 'Not set'
  if (day.is_24h) return 'Open 24 hours'
  if (!day.open_time || !day.close_time) return 'Closed'
  return `${day.open_time.slice(0, 5)}–${day.close_time.slice(0, 5)}`
}
