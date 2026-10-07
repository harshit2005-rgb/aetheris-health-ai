import type { OtpRequested, VerifiedSession } from '@/api/auth'
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
  hospital_name: 'City Care Hospital',
  linked_at: '2026-10-03T09:30:00Z',
  suspended: false,
}

export const lakeside: HospitalLink = {
  hospital_id: 'hosp-2',
  hospital_name: 'Lakeside Clinic',
  linked_at: '2026-09-12T11:00:00Z',
  suspended: true,
}

export const me = (links: HospitalLink[] = []): PatientMe => ({ account, links, pending_policies: [] })
