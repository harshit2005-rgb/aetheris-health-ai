import { CalendarDays } from 'lucide-react'
import ScaffoldPage from '@/components/layout/ScaffoldPage'

export default function AppointmentsPage() {
  return (
    <ScaffoldPage
      title="Appointments"
      subtitle="Booking, queue management and the full appointment lifecycle."
      icon={CalendarDays}
      specRef="Spec Part 6"
      planned={[
        'Day / week / month calendar views',
        'Queue management with tokens',
        'Book appointment form',
        'Status lifecycle workflow',
        'Reschedule & cancellation',
        'Follow-up appointments',
        'AI slot recommendations',
      ]}
    />
  )
}
