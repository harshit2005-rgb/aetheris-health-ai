import type { OtpRequested, VerifiedSession } from '@/api/auth'
import type { PatientHospital } from '@/api/hospitals'
import type { HospitalLink, PatientMe } from '@/api/me'

/** Answers the fake API gives, shaped as the backend contract describes them. */

export const PHONE_TYPED = '+91 98765 43210'
export const PHONE_E164 = '+919876543210'
export const PHONE_MASKED = '+91 •••••• 3210'

export const otpRequested = (challengeId = 'challenge-1'): OtpRequested => ({
  challenge_id: challengeId,
  expires_in: 300,
  resend_after: 60,
})

export const account = { id: 'acct-1', phone_masked: PHONE_MASKED, status: 'active' } as const

export const verifiedSession = (accessToken = 'access-1'): VerifiedSession => ({
  access_token: accessToken,
  expires_in: 900,
  account,
  pending_policies: [],
})

export const cityCare: HospitalLink = {
  hospital_id: 'hosp-1',
  hospital_ref: 'city-care',
  hospital_name: 'City Care Hospital',
  linked_at: '2026-10-03T09:30:00Z',
  suspended: false,
}

export const lakeside: HospitalLink = {
  hospital_id: 'hosp-2',
  hospital_ref: 'lakeside-clinic',
  hospital_name: 'Lakeside Clinic',
  linked_at: '2026-09-12T11:00:00Z',
  suspended: true,
}

export const me = (links: HospitalLink[] = []): PatientMe => ({ account, links, pending_policies: [] })

/** A hospital as `GET /hospitals` describes it: every field present, nothing more. */
export const hospital = (overrides: Partial<PatientHospital> = {}): PatientHospital => ({
  ref: 'city-care',
  name: 'City Care Hospital',
  address: {
    line1: '12 MG Road',
    line2: 'Indiranagar',
    city: 'Bengaluru',
    state: 'Karnataka',
    postal_code: '560038',
    country: 'India',
  },
  phone: '+91 80 5550 0100',
  logo_url: 'https://cdn.example.test/logos/city-care.png',
  timezone: 'Asia/Kolkata',
  linked: false,
  listing: 'standard',
  ...overrides,
})

/** Linked to the signed-in account; has a logo and a phone. */
export const cityCareHospital = hospital({ linked: true })

/** Not linked; no logo, no phone, and only part of an address. */
export const lakesideHospital = hospital({
  ref: 'lakeside-clinic',
  name: 'Lakeside Clinic',
  address: { line1: '4 Lake View Road', line2: null, city: 'Mysuru', state: 'Karnataka', postal_code: null, country: null },
  phone: null,
  logo_url: null,
})

export const sunriseHospital = hospital({
  ref: 'sunrise-medical',
  name: 'Sunrise Medical Centre',
  address: { line1: '88 Residency Road', line2: null, city: 'Bengaluru', state: 'Karnataka', postal_code: '560025', country: 'India' },
  phone: '+91 80 5550 0200',
  logo_url: null,
})

/**
 * A promoted listing. The API never sends one today — no hospital can be
 * promoted — so this exists only to prove the "Sponsored" label is shown the
 * day one is.
 */
export const promotedHospital = hospital({
  ref: 'harbour-health',
  name: 'Harbour Health',
  address: { line1: '1 Dock Street', line2: null, city: 'Kochi', state: 'Kerala', postal_code: '682001', country: 'India' },
  phone: null,
  logo_url: null,
  listing: 'promoted',
})

/** `count` hospitals named so that they sort in order: "Clinic 01", "Clinic 02", … */
export const manyHospitals = (count: number): PatientHospital[] =>
  Array.from({ length: count }, (_, index) => {
    const number = String(index + 1).padStart(2, '0')
    return hospital({ ref: `clinic-${number}`, name: `Clinic ${number}`, phone: null, logo_url: null })
  })
