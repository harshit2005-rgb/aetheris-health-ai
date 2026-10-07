/** English only in V1 (spec 25.6); day-month-year so a date cannot be misread. */
const LOCALE = 'en-GB'

/** True when `value` is a real calendar date written `YYYY-MM-DD`. */
export function isIsoDate(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return false
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])]
  const date = new Date(Date.UTC(year, month - 1, day))
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
}

/** Today in the viewer's own calendar, as `YYYY-MM-DD`. */
export function todayIsoDate(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

/**
 * A calendar date (`YYYY-MM-DD`, no time, no zone) written out in full, e.g.
 * "17 May 1990". Formatted in UTC so the day never shifts with the viewer's
 * zone; echoes the input if it is not a date.
 */
export function formatCalendarDate(iso: string): string {
  if (!isIsoDate(iso)) return iso
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString(LOCALE, {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

/** The day of an ISO instant in the viewer's zone, e.g. "3 Oct 2026"; echoes the input if unparseable. */
export function formatDay(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString(LOCALE, { day: 'numeric', month: 'short', year: 'numeric' })
}
