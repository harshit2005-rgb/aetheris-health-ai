/** E.164: a plus, a country code that does not start with 0, 8–15 digits in all. */
const E164 = /^\+[1-9]\d{7,14}$/

/** An Indian mobile number as people write it at home: 10 digits starting 6–9, optionally after a 0 or 91. */
const INDIAN_MOBILE = /^(?:0|91)?([6-9]\d{9})$/

/**
 * The phone number a patient typed, as E.164 (`+919876543210`), or `null`
 * when it is not one. Spaces, dashes, dots and brackets are how people write
 * numbers and are dropped.
 *
 * The app launches in India, so a number without a plus is read as an Indian
 * mobile: `98765 43210`, `098765 43210` and `91 98765 43210` all become
 * `+919876543210`. Anything else without a plus is refused rather than
 * guessed; other countries need their code.
 */
export function normalisePhone(input: string): string | null {
  const compact = input.replace(/[\s\-.()]/g, '')
  if (compact.startsWith('+')) return E164.test(compact) ? compact : null
  const indian = INDIAN_MOBILE.exec(compact)
  return indian ? `+91${indian[1]}` : null
}
