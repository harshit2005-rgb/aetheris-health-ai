import type { DoctorLeave } from '@/api/doctors'
import { formatDayIn, formatTimeIn, isoDateIn } from '@/lib/format'
import { zonedMidnight } from '@/lib/zonedTime'

/** Whether an instant is midnight on the hospital's clock. */
const atMidnight = (iso: string, timeZone: string) =>
  new Date(zonedMidnight(isoDateIn(iso, timeZone), timeZone)).getTime() === new Date(iso).getTime()

/**
 * A leave in words, on the hospital's clock. A whole-day leave (midnight to
 * midnight, the end exclusive) reads as its first and last days; one recorded
 * with times shows them.
 */
export function describeLeave(leave: DoctorLeave, timeZone: string): string {
  if (atMidnight(leave.starts_at, timeZone) && atMidnight(leave.ends_at, timeZone)) {
    const first = isoDateIn(leave.starts_at, timeZone)
    const last = isoDateIn(new Date(new Date(leave.ends_at).getTime() - 1).toISOString(), timeZone)
    const day = (date: string) => formatDayIn(zonedMidnight(date, timeZone), timeZone)
    return first === last ? day(first) : `${day(first)} – ${day(last)}`
  }
  const at = (iso: string) => `${formatDayIn(iso, timeZone)}, ${formatTimeIn(iso, timeZone)}`
  return `${at(leave.starts_at)} – ${at(leave.ends_at)}`
}

/** Leave not yet over (earliest first, as the API orders it) and leave already over (latest first). */
export function splitLeaves(leaves: DoctorLeave[], now: number): { upcoming: DoctorLeave[]; past: DoctorLeave[] } {
  const ends = (l: DoctorLeave) => new Date(l.ends_at).getTime()
  return {
    upcoming: leaves.filter((l) => ends(l) > now),
    past: leaves.filter((l) => ends(l) <= now).reverse(),
  }
}
