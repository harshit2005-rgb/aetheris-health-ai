import type { Gender } from '@/api/links'

/** User-facing strings of the link and self-registration screens. */
export const linkStrings = {
  title: 'Link a hospital',
  heading: 'Link your hospital record',
  intro: 'Enter the code your hospital gave you and your date of birth. We match them with the mobile number you signed in with.',
  hospitalCodeLabel: 'Hospital code',
  hospitalCodeHint: 'The code your hospital gave you.',
  hospitalCodeRequired: 'Enter the hospital code.',
  dobLabel: 'Date of birth',
  dobRequired: 'Enter your date of birth.',
  dobInvalid: 'Enter a real date.',
  dobFuture: 'Your date of birth cannot be in the future.',
  mrnLabel: 'Medical record number (MRN)',
  mrnHint: 'It is printed on your hospital card, bills and prescriptions.',
  mrnRequired: 'Enter your MRN.',
  mrnNeeded: 'We need your MRN to find your record. Please add it below.',
  // What the tick means, and nothing more: there is no terms-of-service or
  // privacy text yet, so neither tick may claim to accept one.
  linkConsent: 'I agree to connect my app account to my record at this hospital.',
  consentRequired: 'Please tick the box to continue.',
  submit: 'Find my record',
  submitting: 'Checking…',

  // One neutral message for "no record", "wrong date of birth", "wrong MRN" and "unknown hospital".
  notFound: 'We could not find a record with these details.',
  notFoundHelp: 'Check the hospital code and your date of birth and try again.',
  registerOffer: 'New to this hospital? You can register as a new patient instead.',
  registerCta: 'Register as a new patient',
  contactHospital: 'Please contact the hospital.',
  alreadyLinkedElsewhere: 'Your account is already linked to a record at this hospital.',
  invalid: 'Some of these details are not valid. Check them and try again.',
  // A consent version this build no longer matches; a reload fetches the current app.
  reload: 'Please reload and try again.',
  policiesPending: 'We cannot complete this in the app right now. Please try again later.',
  busy: 'Too many attempts. Please wait a few minutes and try again.',
  failed: 'Something went wrong. Check your connection and try again.',

  registerHeading: 'Register as a new patient',
  registerIntro: 'Check your details before we create your record. It will use the mobile number you signed in with.',
  confirmHospitalCode: 'Hospital code',
  confirmDob: 'Date of birth',
  changeDetails: 'These are not right — go back',
  firstNameLabel: 'First name',
  firstNameRequired: 'Enter your first name.',
  lastNameLabel: 'Last name',
  lastNameRequired: 'Enter your last name.',
  nameTooLong: 'This is too long.',
  genderLabel: 'Gender',
  genderRequired: 'Choose an option.',
  genderPlaceholder: 'Choose…',
  registerConsent:
    'I agree to give this hospital my name, date of birth, gender and mobile number to register me as a patient, and to connect my app account to the new record.',
  registerSubmit: 'Create my record',
  registerSubmitting: 'Creating…',
  registerConflict:
    'We could not register you because a record may already exist for you at this hospital. Go back and link it instead, or contact the hospital.',
  registerNotFound:
    'We could not register you with these details. Check the hospital code, or contact the hospital.',

  linkedTitle: 'Your record is linked',
  linkedBody: 'You can now see this hospital on your home screen.',
  alreadyLinkedTitle: 'This record is already linked',
  alreadyLinkedBody: 'Your account was already linked to this record. Nothing has changed.',
  registeredTitle: 'You are registered',
  registeredBody: 'Your new record has been created and linked to your account.',
  goHome: 'Go to home',
} as const

export const genderLabels: Record<Gender, string> = {
  female: 'Female',
  male: 'Male',
  other: 'Other',
  unspecified: 'Prefer not to say',
}
