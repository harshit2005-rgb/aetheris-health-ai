import { CalendarOff } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { Button } from '@atheris/ui'
import type { PatientDoctor } from '@/api/doctors'
import type { PatientHospital } from '@/api/hospitals'
import { BackLink } from '@/components/BackLink'
import { PageHeading } from '@/components/PageHeading'
import { DoctorLoader } from '@/pages/doctors/DoctorLoader'
import { doctorPath } from '@/pages/doctors/paths'
import { doctorStrings as S } from '@/pages/doctors/strings'
import { hospitalPath } from '@/pages/hospitals/paths'

/**
 * Where "View Availability" leads. Availability and booking are not built
 * yet, so this page is only their entry point: it names the doctor (read from
 * the API, so a doctor who is not listed has no such page) and says that
 * there is nothing to show. It has no slots, dates, times, counts or
 * placeholders standing in for them, and it asks the API for nothing about
 * availability.
 */
export function DoctorAvailabilityPage() {
  const { hospitalRef = '', doctorRef = '' } = useParams()
  return (
    <DoctorLoader
      key={`${hospitalRef}/${doctorRef}`}
      hospitalRef={hospitalRef}
      doctorRef={doctorRef}
      title={() => S.availabilityTitle}
    >
      {(doctor, hospital) => <AvailabilityEntry doctor={doctor} hospital={hospital} />}
    </DoctorLoader>
  )
}

function AvailabilityEntry({ doctor, hospital }: { doctor: PatientDoctor; hospital: PatientHospital }) {
  const profile = doctorPath(hospital.ref, doctor.ref)

  return (
    <div className="space-y-6">
      <BackLink to={profile}>{S.backToDoctor(doctor.name)}</BackLink>

      <div className="space-y-1">
        <PageHeading>{S.availabilityHeading}</PageHeading>
        <p className="text-body-lg text-on-surface break-words">{doctor.name}</p>
        {hospital.name && <p className="text-body-sm text-on-surface-variant break-words">{hospital.name}</p>}
      </div>

      <div className="bg-card flex flex-col items-center gap-4 rounded-2xl border px-6 py-10 text-center">
        <span className="bg-surface-container text-outline flex size-14 items-center justify-center rounded-2xl">
          <CalendarOff className="size-7" aria-hidden />
        </span>
        <div className="space-y-1">
          <h2 className="font-display text-title-lg text-primary">{S.availabilityUnavailableTitle}</h2>
          <p className="text-body-sm text-on-surface-variant mx-auto max-w-sm">{S.availabilityUnavailableBody}</p>
        </div>
        <div className="flex w-full flex-col gap-3">
          <Button asChild size="touch" className="w-full">
            <Link to={hospitalPath(hospital.ref)}>{S.hospitalDetails}</Link>
          </Button>
          <Button asChild variant="outline" size="touch" className="w-full">
            <Link to={profile}>{S.backToProfile}</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
