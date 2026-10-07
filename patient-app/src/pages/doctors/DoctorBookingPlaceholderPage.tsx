import { CalendarOff, Link2Off } from 'lucide-react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Button } from '@atheris/ui'
import type { PatientDoctor } from '@/api/doctors'
import type { PatientHospital } from '@/api/hospitals'
import { BackLink } from '@/components/BackLink'
import { PageHeading } from '@/components/PageHeading'
import { formatDay, formatSlotTime, readChosenSlot } from '@/pages/doctors/availability'
import { DoctorLoader } from '@/pages/doctors/DoctorLoader'
import { doctorAvailabilityPath, doctorPath } from '@/pages/doctors/paths'
import { doctorStrings as S } from '@/pages/doctors/strings'

/**
 * Where "Continue to booking" leads. Booking is not built yet, so this page is
 * only its entry point: it names the doctor (read from the API, so a doctor
 * who is not listed has no such page), shows the slot that was chosen, on the
 * hospital's clock, and says that nothing has been booked. It sends nothing:
 * no request reserves, holds or books the slot.
 */
export function DoctorBookingPlaceholderPage() {
  const { hospitalRef = '', doctorRef = '' } = useParams()
  return (
    <DoctorLoader
      key={`${hospitalRef}/${doctorRef}`}
      hospitalRef={hospitalRef}
      doctorRef={doctorRef}
      title={() => S.bookingTitle}
    >
      {(doctor, hospital) => <BookingEntry doctor={doctor} hospital={hospital} />}
    </DoctorLoader>
  )
}

function BookingEntry({ doctor, hospital }: { doctor: PatientDoctor; hospital: PatientHospital }) {
  const [params] = useSearchParams()
  // The link is user input. A slot it names is shown only when every part of
  // it holds together; otherwise nothing of it is shown at all.
  const chosen = readChosenSlot(params, hospital.timezone)
  const availability = doctorAvailabilityPath(
    hospital.ref,
    doctor.ref,
    chosen ? { date: chosen.date, slot: chosen.start } : {},
  )
  const profile = doctorPath(hospital.ref, doctor.ref)

  return (
    <div className="space-y-6">
      <BackLink to={availability}>{S.backToAvailability}</BackLink>

      <header className="space-y-1">
        <PageHeading>{S.bookingHeading}</PageHeading>
        <p className="text-body-lg text-on-surface break-words">{doctor.name}</p>
        {doctor.specialization && <p className="text-body-sm text-on-surface-variant break-words">{doctor.specialization}</p>}
        {hospital.name && <p className="text-body-sm text-on-surface-variant break-words">{hospital.name}</p>}
      </header>

      {chosen ? (
        <>
          <section aria-labelledby="chosen-time" className="bg-card space-y-3 rounded-2xl border p-5">
            <h2 id="chosen-time" className="font-display text-title-lg text-primary">
              {S.chosenTimeHeading}
            </h2>
            <dl className="space-y-2">
              <div>
                <dt className="text-body-sm text-on-surface-variant">{S.chosenDayLabel}</dt>
                <dd className="text-body-lg text-on-surface">{formatDay(chosen.date)}</dd>
              </div>
              <div>
                <dt className="text-body-sm text-on-surface-variant">{S.chosenTimeLabel}</dt>
                <dd className="text-body-lg text-on-surface tabular-nums">
                  {formatSlotTime(chosen.start, hospital.timezone)} – {formatSlotTime(chosen.end, hospital.timezone)}
                </dd>
              </div>
            </dl>
            <p className="text-body-sm text-on-surface-variant break-words">
              {S.timezoneNoteBefore}
              {hospital.timezone}
              {S.timezoneNoteAfter}
            </p>
          </section>

          <div className="bg-card flex flex-col items-center gap-4 rounded-2xl border px-6 py-10 text-center">
            <span className="bg-surface-container text-outline flex size-14 items-center justify-center rounded-2xl">
              <CalendarOff className="size-7" aria-hidden />
            </span>
            <div className="space-y-1">
              <h2 className="font-display text-title-lg text-primary">{S.bookingUnavailableTitle}</h2>
              <p className="text-body-sm text-on-surface-variant mx-auto max-w-sm">{S.bookingUnavailableBody}</p>
            </div>
            <div className="flex w-full flex-col gap-3">
              <Button asChild size="touch" className="w-full">
                <Link to={availability}>{S.backToAvailability}</Link>
              </Button>
              <Button asChild variant="outline" size="touch" className="w-full">
                <Link to={profile}>{S.backToProfile}</Link>
              </Button>
            </div>
          </div>
        </>
      ) : (
        <div className="bg-card flex flex-col items-center gap-4 rounded-2xl border px-6 py-10 text-center">
          <span className="bg-surface-container text-outline flex size-14 items-center justify-center rounded-2xl">
            <Link2Off className="size-7" aria-hidden />
          </span>
          <div className="space-y-1">
            <h2 className="font-display text-title-lg text-primary">{S.invalidLinkTitle}</h2>
            <p className="text-body-sm text-on-surface-variant mx-auto max-w-sm">{S.invalidLinkBody}</p>
          </div>
          <div className="flex w-full flex-col gap-3">
            <Button asChild size="touch" className="w-full">
              <Link to={availability}>{S.goToAvailability}</Link>
            </Button>
            <Button asChild variant="outline" size="touch" className="w-full">
              <Link to={profile}>{S.backToProfile}</Link>
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
