import { Stethoscope } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { Button } from '@atheris/ui'
import type { PatientHospital } from '@/api/hospitals'
import { BackLink } from '@/components/BackLink'
import { PageHeading } from '@/components/PageHeading'
import { doctorStrings as S } from '@/pages/doctors/strings'
import { HospitalLoader } from '@/pages/hospitals/HospitalLoader'
import { hospitalPath } from '@/pages/hospitals/paths'

/**
 * Where "View Doctors" leads. Doctor discovery is not built yet, so this page
 * is only its entry point: it names the hospital (read from the API, like any
 * other hospital page) and says that there is no doctor list to show. It has
 * no doctors, counts, specialties or placeholders standing in for them, and it
 * asks the API for nothing about doctors.
 */
export function HospitalDoctorsPage() {
  const { hospitalRef = '' } = useParams()
  return (
    <HospitalLoader key={hospitalRef} hospitalRef={hospitalRef} title={() => S.title}>
      {(hospital) => <DoctorsEntry hospital={hospital} />}
    </HospitalLoader>
  )
}

function DoctorsEntry({ hospital }: { hospital: PatientHospital }) {
  const back = hospitalPath(hospital.ref)

  return (
    <div className="space-y-6">
      <BackLink to={back}>{hospital.name ? S.backToHospital(hospital.name) : S.backToHospitalFallback}</BackLink>

      <PageHeading>{S.heading(hospital.name)}</PageHeading>

      <div className="bg-card flex flex-col items-center gap-4 rounded-2xl border px-6 py-10 text-center">
        <span className="bg-surface-container text-outline flex size-14 items-center justify-center rounded-2xl">
          <Stethoscope className="size-7" aria-hidden />
        </span>
        <div className="space-y-1">
          <h2 className="font-display text-title-lg text-primary">{S.unavailableTitle}</h2>
          <p className="text-body-sm text-on-surface-variant mx-auto max-w-sm">{S.unavailableBody}</p>
        </div>
        <Button asChild variant="outline" size="touch">
          <Link to={back}>{S.backToHospitalFallback}</Link>
        </Button>
      </div>
    </div>
  )
}
