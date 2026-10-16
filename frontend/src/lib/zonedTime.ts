/**
 * Wall-clock times in a named IANA zone — the hospital's, never the browser's.
 *
 * The API wants instants with an explicit offset (a doctor's leave starts at
 * midnight *in the hospital*), and a browser in another zone, or a zone with a
 * half-hour offset like India's UTC+5:30, must not shift the day.
 */

/** The zone's offset from UTC at an instant, in minutes (India: 330). */
export function offsetMinutesAt(instant: Date, timeZone: string): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(instant)
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0)
  const wall = Date.UTC(get('year'), get('month') - 1, get('day'), get('hour'), get('minute'), get('second'))
  return Math.round((wall - Math.floor(instant.getTime() / 1000) * 1000) / 60_000)
}

/** `+05:30` for 330 minutes, `-04:00` for -240. */
function formatOffset(minutes: number): string {
  const sign = minutes < 0 ? '-' : '+'
  const abs = Math.abs(minutes)
  const hh = String(Math.floor(abs / 60)).padStart(2, '0')
  const mm = String(abs % 60).padStart(2, '0')
  return `${sign}${hh}:${mm}`
}

/**
 * Midnight at the start of a calendar day in a zone, as ISO 8601 with that
 * zone's offset: `zonedMidnight('2026-10-20', 'Asia/Kolkata')` is
 * `2026-10-20T00:00:00+05:30`.
 *
 * @param date `YYYY-MM-DD`.
 * @param timeZone An IANA zone.
 */
export function zonedMidnight(date: string, timeZone: string): string {
  const [y, m, d] = date.split('-').map(Number)
  // The offset at that wall time: guess with the UTC instant of the same wall
  // clock, then correct once, which settles even across a DST change.
  const guess = Date.UTC(y, m - 1, d)
  let offset = offsetMinutesAt(new Date(guess), timeZone)
  offset = offsetMinutesAt(new Date(guess - offset * 60_000), timeZone)
  return `${date}T00:00:00${formatOffset(offset)}`
}

/** The calendar day after `date` (`YYYY-MM-DD`), with no zone involved. */
export function nextDay(date: string): string {
  const [y, m, d] = date.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d + 1)).toISOString().slice(0, 10)
}
