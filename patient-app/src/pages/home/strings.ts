/** User-facing strings of the home screen. */
export const homeStrings = {
  title: 'Home',
  heading: 'Welcome',
  signedInAs: 'Signed in as',
  hospitalsHeading: 'Your hospitals',
  linkedOn: (day: string) => `Linked on ${day}`,
  active: 'Linked',
  paused: 'Paused',
  pausedHelp:
    'The mobile number on this hospital record is different from the one you signed in with. Please contact the hospital to update it.',
  emptyTitle: 'No hospital linked yet',
  emptyBody: 'Link your hospital record to see your care in one place. You will need the code your hospital gave you.',
  linkFirst: 'Link a hospital record',
  linkAnother: 'Link another hospital',
  loading: 'Loading your details…',
  loadFailed: 'We could not load your details. Check your connection and try again.',
  retry: 'Try again',
  signOut: 'Sign out',
  signingOut: 'Signing out…',
  signOutFailed: 'We could not sign you out. Check your connection and try again.',
} as const
