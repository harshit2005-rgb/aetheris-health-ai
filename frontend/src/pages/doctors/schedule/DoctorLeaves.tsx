import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { CalendarOff, Plus, RotateCw, X } from 'lucide-react'
import { FormDialog } from '@/components/forms/FormDialog'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { useCreateLeave, useDeleteLeave, useDoctorLeaves, type DoctorLeave } from '@/api/doctors'
import { isoDateIn } from '@/lib/format'
import { nextDay, zonedMidnight } from '@/lib/zonedTime'
import { describeLeave, splitLeaves } from './leaveText'

const DATE = /^\d{4}-\d{2}-\d{2}$/

const leaveSchema = z
  .object({
    from: z.string().regex(DATE, 'Choose the first day of leave'),
    to: z.string().regex(DATE, 'Choose the last day of leave'),
    reason: z.string().trim().max(200, 'At most 200 characters'),
  })
  .refine((v) => v.to >= v.from, { path: ['to'], message: 'The last day must be on or after the first' })
type LeaveValues = z.infer<typeof leaveSchema>

const confirmSchema = z.object({})

/**
 * A doctor's time off (module spec §5.3): recorded whole days, auto-approved,
 * on the hospital's clock. Anyone who may see the doctor sees it; someone who
 * may change this doctor's schedule records and cancels it.
 */
export function DoctorLeaves({
  doctorId,
  doctorName,
  timeZone,
  canEdit,
}: {
  doctorId: string
  doctorName: string
  timeZone: string
  canEdit: boolean
}) {
  const { data: leaves, isPending, isError, refetch } = useDoctorLeaves(doctorId)
  // Read once per visit: which leave is "upcoming" does not change while the card is open.
  const [now] = useState(() => Date.now())
  const { upcoming, past } = splitLeaves(leaves ?? [], now)

  return (
    <section aria-labelledby="leave-heading" className="neo-extruded bg-surface space-y-4 rounded-2xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="leave-heading" className="font-display text-title-lg text-primary flex items-center gap-2 font-bold">
          <CalendarOff className="size-5" aria-hidden /> Leave
        </h2>
        {canEdit && <AddLeaveDialog doctorId={doctorId} doctorName={doctorName} timeZone={timeZone} />}
      </div>

      {isPending ? (
        <Skeleton className="h-16 w-full rounded-xl" aria-label="Loading leave" />
      ) : isError ? (
        <Alert variant="error" title="Couldn't load leave">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RotateCw className="size-4" aria-hidden /> Retry
          </Button>
        </Alert>
      ) : (
        <>
          {upcoming.length === 0 ? (
            <p className="font-body text-body-md text-on-surface-variant">No upcoming leave.</p>
          ) : (
            <ul aria-label="Upcoming leave" className="divide-outline-variant/40 divide-y">
              {upcoming.map((leave) => (
                <li key={leave.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div>
                    <p className="font-body text-body-md text-on-surface font-semibold">{describeLeave(leave, timeZone)}</p>
                    {leave.reason && <p className="font-body text-body-sm text-on-surface-variant">{leave.reason}</p>}
                  </div>
                  {canEdit && (
                    <CancelLeaveDialog doctorId={doctorId} leave={leave} label={describeLeave(leave, timeZone)} />
                  )}
                </li>
              ))}
            </ul>
          )}
          {past.length > 0 && (
            <details>
              <summary className="font-body text-body-sm text-secondary cursor-pointer">
                Past leave ({past.length})
              </summary>
              <ul aria-label="Past leave" className="mt-2 space-y-1">
                {past.map((leave) => (
                  <li key={leave.id} className="font-body text-body-sm text-on-surface-variant">
                    {describeLeave(leave, timeZone)}
                    {leave.reason ? ` · ${leave.reason}` : ''}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </section>
  )
}

function AddLeaveDialog({ doctorId, doctorName, timeZone }: { doctorId: string; doctorName: string; timeZone: string }) {
  const create = useCreateLeave(doctorId)
  return (
    <FormDialog<LeaveValues>
      trigger={
        <Button variant="outline" size="sm">
          <Plus className="size-4" aria-hidden /> Add leave
        </Button>
      }
      title="Add leave"
      description={
        <>
          {doctorName} can&apos;t be booked on these days. Whole days, on the hospital&apos;s clock ({timeZone}).
        </>
      }
      resolver={zodResolver(leaveSchema)}
      defaults={() => {
        // Today on the hospital's clock, not the browser's.
        const today = isoDateIn(new Date().toISOString(), timeZone)
        return { from: today, to: today, reason: '' }
      }}
      submitLabel="Add leave"
      pendingLabel="Adding…"
      fallbackError="Couldn't add the leave. Try again."
      onSubmit={async (v) => {
        await create.mutateAsync({
          starts_at: zonedMidnight(v.from, timeZone),
          ends_at: zonedMidnight(nextDay(v.to), timeZone),
          ...(v.reason ? { reason: v.reason } : {}),
        })
        return 'Leave added'
      }}
    >
      {({ register, formState: { errors } }) => (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="First day" required error={errors.from?.message}>
            {(p) => <Input type="date" {...p} {...register('from')} />}
          </Field>
          <Field label="Last day" required error={errors.to?.message}>
            {(p) => <Input type="date" {...p} {...register('to')} />}
          </Field>
          <Field label="Reason" error={errors.reason?.message} className="sm:col-span-2">
            {(p) => <Textarea rows={2} {...p} {...register('reason')} />}
          </Field>
        </div>
      )}
    </FormDialog>
  )
}

function CancelLeaveDialog({ doctorId, leave, label }: { doctorId: string; leave: DoctorLeave; label: string }) {
  const remove = useDeleteLeave(doctorId)
  return (
    <FormDialog<Record<string, never>>
      trigger={
        <Button variant="ghost" size="sm" className="text-error" aria-label={`Cancel leave ${label}`}>
          <X className="size-4" aria-hidden /> Cancel leave
        </Button>
      }
      title="Cancel this leave?"
      description={<>{label}: these days become bookable again.</>}
      resolver={zodResolver(confirmSchema)}
      defaults={() => ({})}
      submitLabel="Cancel leave"
      pendingLabel="Cancelling…"
      destructive
      dismissLabel="Keep leave"
      fallbackError="Couldn't cancel the leave. Try again."
      onSubmit={async () => {
        await remove.mutateAsync(leave.id)
        return 'Leave cancelled'
      }}
    >
      {() => null}
    </FormDialog>
  )
}
