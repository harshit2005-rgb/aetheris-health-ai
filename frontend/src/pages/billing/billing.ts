import type { PaymentMethod } from '@/api/billing'
import { ApiError } from '@/api/types'

export const PAYMENT_METHOD_LABEL: Record<PaymentMethod, string> = {
  cash: 'Cash',
  card: 'Card',
  upi: 'UPI',
  bank_transfer: 'Bank transfer',
  insurance: 'Insurance',
}

export const PAYMENT_METHODS = Object.keys(PAYMENT_METHOD_LABEL) as PaymentMethod[]

/**
 * What the API accepts as an amount: digits with at most two decimals
 * (docs/18-API_CONTRACTS.md §6.2). This only checks that the text is a money
 * value — whether it is too much is the server's call.
 */
export const MONEY_PATTERN = /^\d+(\.\d{1,2})?$/

/** True for a well-formed amount above zero, compared as text so no float is involved. */
export function isPositiveMoney(value: string): boolean {
  return MONEY_PATTERN.test(value) && /[1-9]/.test(value)
}

export interface FieldError {
  field: string
  message: string
}

/**
 * Field-level errors from a 422. Request validation sends a list; a rule the
 * billing service enforces sends `{ errors: [...] }` — both name the field the
 * same way (`discount_amount`, `items.1.service_id`).
 */
export function fieldErrorsOf(err: unknown): FieldError[] {
  if (!(err instanceof ApiError) || err.status !== 422) return []
  const details = err.details as unknown
  const list = Array.isArray(details)
    ? details
    : Array.isArray((details as { errors?: unknown } | null)?.errors)
      ? (details as { errors: unknown[] }).errors
      : []
  return list.filter(
    (e): e is FieldError =>
      typeof (e as FieldError)?.field === 'string' && typeof (e as FieldError)?.message === 'string',
  )
}

/**
 * The message to show for a failed billing call. The API's own wording is used
 * for the outcomes it writes for users — a rule broken (400), not allowed
 * (403), gone (404), a conflict (409), invalid input (422). Anything else
 * (a 5xx, the network) gets the caller's fallback rather than internal text.
 */
export function billingErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError && [400, 403, 404, 409, 422].includes(err.status ?? 0)) {
    return err.message
  }
  return fallback
}

/**
 * Split a 422's field errors into those a form can show under a field and the
 * rest, which belong above the form. `isFormField` decides which is which.
 */
export function splitFieldErrors(
  err: unknown,
  isFormField: (field: string) => boolean,
): { onFields: FieldError[]; other: string[] } {
  const all = fieldErrorsOf(err)
  return {
    onFields: all.filter((e) => isFormField(e.field)),
    other: all.filter((e) => !isFormField(e.field)).map((e) => e.message),
  }
}
