import { hospitalDoctorsPath } from '@/pages/hospitals/paths'

/**
 * Where a doctor's pages live in the app, under their hospital. Both
 * references come from the server and are escaped, so each can only ever be
 * one path segment.
 */
export const doctorPath = (hospitalRef: string, doctorRef: string) =>
  `${hospitalDoctorsPath(hospitalRef)}/${encodeURIComponent(doctorRef)}`

export const doctorAvailabilityPath = (hospitalRef: string, doctorRef: string) =>
  `${doctorPath(hospitalRef, doctorRef)}/availability`
