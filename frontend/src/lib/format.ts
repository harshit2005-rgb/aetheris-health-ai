/**
 * Formatting helpers. Money is rendered with a currency the caller supplies
 * (the hospital's currency, from user context); until that is wired the default
 * is a plain 2-decimal amount with no symbol, so we never imply the wrong one.
 */
export function formatMoney(value: string | number, currency?: string): string {
  const amount = typeof value === 'string' ? Number(value) : value
  if (Number.isNaN(amount)) return '—'
  if (currency) {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount)
  }
  return new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount)
}

/** Medium date (e.g. "2 May 1971") from an ISO string; echoes the input if unparseable. */
export function formatDate(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { dateStyle: 'medium' })
}

/** Short local time (e.g. "9:30 AM") from an ISO datetime; echoes the input if unparseable. */
export function formatTime(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleTimeString(undefined, { timeStyle: 'short' })
}

/**
 * Short time in a named IANA zone — for times that belong to the hospital's
 * clock (a doctor's slots), which is not necessarily the viewer's. Without a
 * zone, or with one the browser does not know, the viewer's clock is used.
 */
export function formatTimeIn(iso: string, timeZone?: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  try {
    return d.toLocaleTimeString(undefined, { timeStyle: 'short', timeZone })
  } catch {
    return d.toLocaleTimeString(undefined, { timeStyle: 'short' })
  }
}

/** Day with its weekday (e.g. "Tue, 6 Oct 2026") in a named IANA zone; see {@link formatTimeIn}. */
export function formatDayIn(iso: string, timeZone?: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const style = { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' } as const
  try {
    return d.toLocaleDateString(undefined, { ...style, timeZone })
  } catch {
    return d.toLocaleDateString(undefined, style)
  }
}

/**
 * The calendar day (YYYY-MM-DD) an instant falls on in a named IANA zone — the
 * value a date input and the API's day filters expect. See {@link formatTimeIn}.
 */
export function isoDateIn(iso: string, timeZone?: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const parts = (zone?: string) => {
    const p = new Intl.DateTimeFormat('en-US', {
      timeZone: zone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(d)
    const get = (type: string) => p.find((x) => x.type === type)?.value ?? ''
    return `${get('year')}-${get('month')}-${get('day')}`
  }
  try {
    return parts(timeZone)
  } catch {
    return parts()
  }
}

/**
 * How long ago something happened, in the viewer's language: "now",
 * "5 minutes ago", "yesterday". Past a week it is clearer as a date, so it
 * falls back to {@link formatDate}. `now` is injectable for tests.
 */
export function formatRelativeTime(iso: string, now: number = Date.now()): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return iso
  const seconds = Math.round((then - now) / 1000)
  const elapsed = Math.abs(seconds)
  const relative = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
  if (elapsed < 45) return relative.format(0, 'second')
  if (elapsed < 3600) return relative.format(Math.round(seconds / 60), 'minute')
  if (elapsed < 86_400) return relative.format(Math.round(seconds / 3600), 'hour')
  if (elapsed < 7 * 86_400) return relative.format(Math.round(seconds / 86_400), 'day')
  return formatDate(iso)
}

/** Today's date in the viewer's local timezone as YYYY-MM-DD (for date inputs and day filters). */
export function todayISODate(): string {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}
