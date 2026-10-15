import { CalendarDays, Search } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Alert, Button, Skeleton } from '@atheris/ui'
import { useMyAppointments } from '@/api/myAppointments'
import { AppointmentCard } from '@/pages/appointments/AppointmentCard'
import { APPOINTMENTS_PATH } from '@/pages/appointments/paths'
import { homeStrings as S } from '@/pages/home/strings'

/**
 * The patient's next appointment, read from the first page of the upcoming
 * list: the server puts the soonest first, so nothing here sorts, filters or
 * reads the clock. It fails on its own, without taking the rest of home with it.
 */
export function NextAppointment() {
  const upcoming = useMyAppointments({ scope: 'upcoming', page: 1 })
  const next = upcoming.data?.items[0]

  return (
    <section aria-labelledby="next-heading" className="space-y-3">
      <h2 id="next-heading" className="font-display text-title-lg text-primary">
        {S.nextHeading}
      </h2>

      {upcoming.isPending ? (
        <div role="status" aria-label={S.nextLoading}>
          <Skeleton className="h-40 w-full rounded-2xl" />
        </div>
      ) : upcoming.isError ? (
        <div className="space-y-3">
          <Alert variant="error">{S.nextLoadFailed}</Alert>
          <Button variant="outline" size="touch" onClick={() => void upcoming.refetch()} disabled={upcoming.isFetching}>
            {S.retry}
          </Button>
        </div>
      ) : next ? (
        <>
          <ul aria-labelledby="next-heading">
            <AppointmentCard appointment={next} offerCancel={false} />
          </ul>
          <Button asChild variant="ghost" size="touch" className="text-secondary w-full">
            <Link to={APPOINTMENTS_PATH}>
              <CalendarDays aria-hidden />
              {S.allAppointments}
            </Link>
          </Button>
        </>
      ) : (
        <div className="bg-card space-y-3 rounded-2xl border p-5">
          <p className="text-body-lg text-on-surface font-semibold">{S.noUpcomingTitle}</p>
          <p className="text-body-sm text-on-surface-variant">{S.noUpcomingBody}</p>
          <div className="flex flex-col gap-2">
            <Button asChild size="touch" className="w-full">
              <Link to="/hospitals">
                <Search aria-hidden />
                {S.bookCta}
              </Link>
            </Button>
            <Button asChild variant="outline" size="touch" className="w-full">
              <Link to={APPOINTMENTS_PATH}>
                <CalendarDays aria-hidden />
                {S.appointmentsCta}
              </Link>
            </Button>
          </div>
        </div>
      )}
    </section>
  )
}
