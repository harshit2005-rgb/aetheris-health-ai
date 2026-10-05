import { useRef } from 'react'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAppointmentTransition, type AppointmentSummary } from '@/api/appointments'
import { usePermissions } from '@/hooks/usePermissions'
import { CancelAppointmentDialog } from './CancelAppointmentDialog'
import { RescheduleAppointmentDialog } from './RescheduleAppointmentDialog'
import { CANCELLABLE, NEXT_STEP, RESCHEDULABLE, lifecycleErrorMessage } from './lifecycle'

/**
 * The lifecycle actions for one queue row: the next step for its status, plus
 * Reschedule and Cancel where the API allows them. An action the user's permissions don't cover
 * is not rendered — a convenience only; the backend enforces each one.
 */
export function AppointmentActions({ appointment }: { appointment: AppointmentSummary }) {
  const { can } = usePermissions()
  const transition = useAppointmentTransition()
  // `isPending` only disables the button after a re-render; this also stops a
  // second click fired before that happens.
  const busy = useRef(false)

  const step = NEXT_STEP[appointment.status]
  const next = step && can(step.permission) ? step : undefined
  const canCancel = CANCELLABLE.has(appointment.status) && can('appointment.cancel')
  // The new time is picked from the doctor's slots, which need their own permission.
  const canReschedule =
    RESCHEDULABLE.has(appointment.status) &&
    can('appointment.reschedule') &&
    can('doctor.availability.read')
  if (!next && !canCancel && !canReschedule) return null

  async function run() {
    if (!next || busy.current) return
    busy.current = true
    try {
      await transition.mutateAsync({ id: appointment.id, action: next.action })
      toast.success(next.done)
    } catch (err) {
      toast.error(lifecycleErrorMessage(err, next))
    } finally {
      busy.current = false
    }
  }

  const Icon = next?.icon
  return (
    <div className="flex flex-wrap justify-end gap-2">
      {next && Icon && (
        <Button
          variant="outline"
          size="sm"
          disabled={transition.isPending}
          aria-busy={transition.isPending}
          aria-label={`${next.label} ${appointment.patient_name}`}
          onClick={() => run()}
        >
          {transition.isPending ? <Loader2 className="size-4 animate-spin" /> : <Icon className="size-4" />}
          {transition.isPending ? next.pendingLabel : next.label}
        </Button>
      )}
      {canReschedule && (
        <RescheduleAppointmentDialog appointment={appointment} disabled={transition.isPending} />
      )}
      {canCancel && <CancelAppointmentDialog appointment={appointment} disabled={transition.isPending} />}
    </div>
  )
}
