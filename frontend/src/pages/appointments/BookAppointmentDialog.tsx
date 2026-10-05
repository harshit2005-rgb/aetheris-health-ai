import { type ReactNode, useRef, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Check, Loader2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Alert } from '@/components/ui/alert'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { PatientPicker } from '@/components/patients/PatientPicker'
import { useDoctors } from '@/api/doctors'
import { useBookAppointment, type AppointmentType, type BookAppointmentInput } from '@/api/appointments'
import { ApiError } from '@/api/types'

const TYPES: { value: AppointmentType; label: string }[] = [
  { value: 'new', label: 'New' },
  { value: 'follow_up', label: 'Follow-up' },
  { value: 'walk_in', label: 'Walk-in' },
  { value: 'emergency', label: 'Emergency' },
]

const DURATIONS = [15, 30, 45, 60]

const schema = z.object({
  patient_id: z.string().min(1, 'Choose a patient'),
  doctor_id: z.string().min(1, 'Choose a doctor'),
  date: z.string().min(1, 'Pick a date'),
  time: z.string().min(1, 'Pick a time'),
  duration: z.coerce.number().int().positive(),
  type: z.enum(['new', 'follow_up', 'walk_in', 'emergency']),
  // Module spec §11: the API rejects a reason over 500 characters.
  reason: z.string().max(500, 'Keep the reason under 500 characters').optional(),
})

type FormValues = z.input<typeof schema>

/** Where a field named in a 422 from the API is shown on this form. */
const SERVER_FIELDS: Record<string, keyof FormValues> = {
  patient_id: 'patient_id',
  doctor_id: 'doctor_id',
  scheduled_start: 'time',
  scheduled_end: 'time',
  type: 'type',
  reason: 'reason',
}

interface Notice {
  variant: 'warning' | 'error'
  title: string
  body: string
}

/** Basic appointment booking: patient + doctor + time + type. Handles the 409 conflict. */
export function BookAppointmentDialog({ trigger }: { trigger: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [notice, setNotice] = useState<Notice | null>(null)
  // `isPending` only disables the button after a re-render; this also stops a
  // second submit (double click, Enter held down) fired before that happens.
  const submitting = useRef(false)
  const book = useBookAppointment()
  const { data: doctorsPage } = useDoctors({ page: 1, page_size: 100 })
  const doctors = doctorsPage?.items ?? []

  const {
    control,
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { patient_id: '', doctor_id: '', date: '', time: '', duration: 15, type: 'new', reason: '' },
  })

  function closeAndReset(next: boolean) {
    setOpen(next)
    if (!next) {
      reset()
      setNotice(null)
    }
  }

  async function onSubmit(values: FormValues) {
    if (submitting.current) return
    setNotice(null)
    const start = new Date(`${values.date}T${values.time}`)
    if (Number.isNaN(start.getTime())) {
      setError('date', { message: 'Enter a valid date and time' })
      return
    }
    const durationMin = Number(values.duration)
    const payload: BookAppointmentInput = {
      patient_id: values.patient_id,
      doctor_id: values.doctor_id,
      scheduled_start: start.toISOString(),
      scheduled_end: new Date(start.getTime() + durationMin * 60_000).toISOString(),
      type: values.type,
      ...(values.reason ? { reason: values.reason } : {}),
    }

    submitting.current = true
    try {
      await book.mutateAsync(payload)
      toast.success('Appointment booked')
      closeAndReset(false)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setNotice({
          variant: 'warning',
          title: 'Time unavailable',
          body: 'That doctor already has an appointment in this window. Pick another time.',
        })
        return
      }
      if (err instanceof ApiError && Array.isArray(err.details)) {
        const fieldErrors = err.details as Array<{ field?: string; message?: string }>
        const unmapped: string[] = []
        for (const fe of fieldErrors) {
          const target = fe.field ? SERVER_FIELDS[fe.field] : undefined
          if (target) setError(target, { message: fe.message ?? 'Invalid value' })
          else if (fe.message) unmapped.push(fe.message)
        }
        // Errors about the whole request (the booking window, a header) have no
        // field to sit under, so they are shown above the form instead.
        if (unmapped.length > 0) {
          setNotice({ variant: 'error', title: "Couldn't book", body: unmapped.join(' ') })
        }
        return
      }
      // 400 is a business rule the user can act on, e.g. outside availability.
      if (err instanceof ApiError && (err.status === 400 || err.status === 422)) {
        setNotice({ variant: 'error', title: "Couldn't book", body: err.message })
        return
      }
      toast.error(err instanceof ApiError ? err.message : 'Could not book the appointment.')
    } finally {
      submitting.current = false
    }
  }

  return (
    <Dialog open={open} onOpenChange={closeAndReset}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Book appointment</DialogTitle>
          <DialogDescription>Schedule a patient with a doctor.</DialogDescription>
        </DialogHeader>

        <form onSubmit={(e) => handleSubmit(onSubmit)(e)} className="space-y-4" noValidate>
          {notice && (
            <Alert variant={notice.variant} title={notice.title}>
              {notice.body}
            </Alert>
          )}

          <Controller
            control={control}
            name="patient_id"
            render={({ field }) => (
              <Field label="Patient" required error={errors.patient_id?.message}>
                {(p) => (
                  <PatientPicker
                    id={p.id}
                    value={field.value}
                    onChange={field.onChange}
                    invalid={p['aria-invalid']}
                  />
                )}
              </Field>
            )}
          />

          <Controller
            control={control}
            name="doctor_id"
            render={({ field }) => (
              <Field label="Doctor" required error={errors.doctor_id?.message}>
                {(p) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id={p.id} aria-invalid={p['aria-invalid']}>
                      <SelectValue placeholder="Select a doctor" />
                    </SelectTrigger>
                    <SelectContent>
                      {doctors.map((d) => (
                        <SelectItem key={d.id} value={d.id}>
                          {d.full_name} · {d.specialization}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </Field>
            )}
          />

          <div className="grid grid-cols-2 gap-4">
            <Field label="Date" required error={errors.date?.message}>
              {(p) => <Input type="date" {...p} {...register('date')} />}
            </Field>
            <Field label="Time" required error={errors.time?.message}>
              {(p) => <Input type="time" {...p} {...register('time')} />}
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Controller
              control={control}
              name="duration"
              render={({ field }) => (
                <Field label="Duration" required error={errors.duration?.message}>
                  {(p) => (
                    <Select value={String(field.value)} onValueChange={(v) => field.onChange(Number(v))}>
                      <SelectTrigger id={p.id} aria-invalid={p['aria-invalid']}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {DURATIONS.map((d) => (
                          <SelectItem key={d} value={String(d)}>
                            {d} min
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </Field>
              )}
            />
            <Controller
              control={control}
              name="type"
              render={({ field }) => (
                <Field label="Type" required error={errors.type?.message}>
                  {(p) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id={p.id} aria-invalid={p['aria-invalid']}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {TYPES.map((t) => (
                          <SelectItem key={t.value} value={t.value}>
                            {t.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </Field>
              )}
            />
          </div>

          <Field label="Reason" hint="Optional" error={errors.reason?.message}>
            {(p) => <Textarea rows={2} placeholder="e.g. Persistent cough" {...p} {...register('reason')} />}
          </Field>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => closeAndReset(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={book.isPending} aria-busy={book.isPending}>
              {book.isPending ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
              {book.isPending ? 'Booking…' : 'Book'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
