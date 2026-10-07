/** User-facing strings of doctor discovery: a hospital's doctors, one doctor, and the way on to availability. */
export const doctorStrings = {
  title: 'Doctors',
  heading: (hospital: string) => `Doctors at ${hospital}`,
  headingFallback: 'Doctors',
  listIntro: 'Search the doctors listed at this hospital.',
  backToHospital: (hospital: string) => `Back to ${hospital}`,
  backToHospitalFallback: 'Back to the hospital',

  searchFormLabel: 'Find a doctor',
  searchLabel: 'Search by name or specialisation',
  clearSearch: 'Clear search',
  departmentLabel: 'Department',
  allDepartments: 'All departments',
  // A department in force that the list of departments does not name. Its reference is never shown.
  selectedDepartment: 'Selected department',

  resultsHeading: 'Doctors',
  loading: 'Loading doctors…',
  // The position in the results, exactly as the server reported it.
  count: (total: number) => (total === 1 ? '1 doctor' : `${total} doctors`),
  range: (from: number, to: number, total: number) => `Showing ${from}–${to} of ${total} doctors`,
  paginationLabel: 'Pages of doctors',
  pageOf: (page: number, pages: number) => `Page ${page} of ${pages}`,
  previous: 'Previous',
  next: 'Next',

  // Two different kinds of nothing: none are listed, or none match.
  noneStatus: 'No doctors to show',
  noneTitle: 'No doctors listed yet',
  noneBody: 'This hospital has no doctors listed in the app right now. Please check again later.',
  noMatchStatus: 'No doctors match',
  noMatchTitle: 'No doctors match your search',
  noMatchBody: 'Check the spelling, or clear the search and the department to see every doctor.',
  clearFilters: 'Clear search and department',
  pastEndStatus: 'Nothing on this page',
  pastEndTitle: 'There is nothing on this page',
  pastEndBody: (total: number) =>
    total === 1 ? 'There is 1 doctor in all, on the first page.' : `There are ${total} doctors in all, on earlier pages.`,
  firstPage: 'Go to the first page',

  listFailed: 'We could not load the doctors. Please try again.',
  doctorFailed: 'We could not load this doctor. Please try again.',

  viewProfile: 'View Profile',
  qualificationsLabel: 'Qualifications',
  languagesLabel: 'Languages',
  // How a list of degrees or languages is joined on one line.
  listSeparator: ', ',

  profileTitle: 'Doctor',
  loadingDoctor: 'Loading doctor…',
  allDoctors: (hospital: string) => `Doctors at ${hospital}`,
  allDoctorsFallback: 'All doctors',
  hospitalLabel: 'Hospital',
  hospitalFallback: 'View the hospital',
  aboutHeading: 'About',
  viewAvailability: 'View Availability',

  // One neutral message for "no such doctor", "not listed" and "not at this hospital".
  notFoundTitle: 'This doctor is not available',
  notFoundBody: 'They may not be listed in the app, or the link you followed may be wrong.',
  browseDoctors: 'Browse doctors',

  availabilityTitle: 'Availability',
  availabilityHeading: 'Availability',
  // Said as it is: the app has no availability to show and no date for it.
  availabilityUnavailableTitle: 'Availability and booking are not in the app yet',
  availabilityUnavailableBody:
    'You cannot see when this doctor is available or book an appointment in the app yet. For now, please contact the hospital directly.',
  backToProfile: 'Back to the profile',
  backToDoctor: (doctor: string) => `Back to ${doctor}`,
  hospitalDetails: 'Hospital contact details',
} as const
