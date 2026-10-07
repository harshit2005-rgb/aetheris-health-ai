/** User-facing strings of doctor discovery: a hospital's doctors, one doctor, their availability, and the way on to booking. */
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

  backToProfile: 'Back to the profile',
  backToDoctor: (doctor: string) => `Back to ${doctor}`,

  // Availability: the free slots the server returned, on the hospital's clock, and nothing more.
  availabilityTitle: 'Availability',
  availabilityHeading: 'Availability',
  loadingAvailability: 'Loading availability…',
  // The zone is the server's text; it is shown as it is, inside this sentence.
  timezoneNoteBefore: 'Times are in the hospital’s local time (',
  timezoneNoteAfter: ')',
  notReserved: 'Seeing a free slot does not reserve it — it can be taken until the booking is confirmed.',

  daysHeading: 'Choose a day',
  daysLabel: 'Days',
  earlierDays: 'Earlier days',
  laterDays: 'Later days',
  windowRange: (from: string, to: string) => (from === to ? from : `${from} – ${to}`),
  today: 'Today',
  // On a day chip: how many free slots the server returned for that day.
  slotCount: (count: number) => (count === 1 ? '1 slot' : `${count} slots`),
  noSlotsOnChip: 'No slots',
  dayLabel: (day: string, count: number) =>
    `${day}, ${count === 0 ? 'no free slots' : count === 1 ? '1 free slot' : `${count} free slots`}`,

  timesHeading: 'Choose a time',
  timesLabel: (day: string) => `Times on ${day}`,
  slotLabel: (from: string, to: string, day: string) => `${from} to ${to}, ${day}`,
  // The live line under "Choose a time".
  dayStatus: (count: number, day: string) =>
    count === 0 ? `No free slots on ${day}` : count === 1 ? `1 free slot on ${day}` : `${count} free slots on ${day}`,
  windowStatus: (from: string, to: string) => (from === to ? `No free slots on ${from}` : `No free slots from ${from} to ${to}`),
  emptyDayTitle: 'No free slots on this day',
  emptyDayBody: 'Choose another day, or look at the days after these.',
  emptyWindowTitle: 'No free slots in these days',
  emptyWindowBody: 'Look at the days before or after these, or check again later.',
  // A slot that was in the address but is not among the free ones any more.
  slotGone: 'That time is no longer free.',

  availabilityFailed: 'We could not load the availability. Please try again.',
  // The server refused the dates: the bookable days have moved on since the page was opened.
  dateGoneTitle: 'This date is no longer available',
  dateGoneBody: 'The days that can be booked have moved on. Start again from today.',
  goToToday: 'Go to today',

  selectionHeading: 'Your selection',
  selectionHint: 'Choose a day and a time to continue.',
  selectionSummary: (day: string, from: string, to: string) => `${day}, ${from} to ${to}`,
  clearSelection: 'Clear selection',
  continueToBooking: 'Continue to booking',

  // The booking step itself is not in the app yet: the chosen slot is shown back, and nothing is reserved.
  bookingTitle: 'Booking',
  bookingHeading: 'Booking',
  chosenTimeHeading: 'Your chosen time',
  chosenDayLabel: 'Day',
  chosenTimeLabel: 'Time',
  bookingUnavailableTitle: 'Booking is not available in the app yet',
  bookingUnavailableBody: 'This slot is not reserved. For now, please contact the hospital to book an appointment.',
  invalidLinkTitle: 'This booking link is not valid',
  invalidLinkBody: 'Choose a day and a time from the doctor’s availability to continue.',
  backToAvailability: 'Back to availability',
  goToAvailability: 'Go to availability',
} as const
