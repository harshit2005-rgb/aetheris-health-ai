/** User-facing strings of doctor discovery. Only its entry point exists so far. */
export const doctorStrings = {
  title: 'Doctors',
  heading: (hospital: string) => `Doctors at ${hospital}`,
  // Said as it is: there is no doctor list in the app yet, and no date for one.
  unavailableTitle: 'Doctor listings are not available yet',
  unavailableBody:
    'You cannot browse or book the doctors at this hospital in the app yet. For now, please contact the hospital directly.',
  backToHospital: (hospital: string) => `Back to ${hospital}`,
  backToHospitalFallback: 'Back to the hospital',
} as const
