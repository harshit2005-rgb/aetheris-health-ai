import { type ReactNode, useState } from 'react'
import { Controller, type Path, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { useCreatePatient, type BloodGroup, type CreatePatientInput } from '@/api/patients'
import { ApiError } from '@/api/types'

const GENDERS: { value: CreatePatientInput['gender']; label: string }[] = [
  { value: 'male', label: 'Male' },
  { value: 'female', label: 'Female' },
  { value: 'other', label: 'Other' },
  { value: 'unspecified', label: 'Unspecified' },
]

const BLOOD_GROUPS: BloodGroup[] = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

// Mirrors the required/optional split in CreatePatientRequest. The backend is the
// authority on format (E.164 phone, age bounds); the frontend catches the obvious.
const schema = z.object({
  first_name: z.string().trim().min(1, 'First name is required').max(100),
  last_name: z.string().trim().min(1, 'Last name is required').max(100),
  date_of_birth: z
    .string()
    .min(1, 'Date of birth is required')
    .refine((v) => !Number.isNaN(Date.parse(v)) && new Date(v) <= new Date(), 'Enter a valid past date'),
  gender: z.enum(['male', 'female', 'other', 'unspecified'], { message: 'Select a gender' }),
  blood_group: z.enum(['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']).optional(),
  phone: z.string().trim().optional(),
  email: z.string().trim().email('Enter a valid email').optional().or(z.literal('')),
})

type FormValues = z.infer<typeof schema>

/** Reference create flow: Dialog + form kit + RHF/Zod + the real create endpoint. */
export function RegisterPatientDialog({ trigger }: { trigger: ReactNode }) {
  const [open, setOpen] = useState(false)
  const createPatient = useCreatePatient()

  const {
    register,
    control,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { first_name: '', last_name: '', date_of_birth: '', phone: '', email: '' },
  })

  async function onSubmit(values: FormValues) {
    // Drop empty optionals so we never send "" for a field the backend treats as absent.
    const payload: CreatePatientInput = {
      first_name: values.first_name,
      last_name: values.last_name,
      date_of_birth: values.date_of_birth,
      gender: values.gender,
      ...(values.blood_group ? { blood_group: values.blood_group } : {}),
      ...(values.phone ? { phone: values.phone } : {}),
      ...(values.email ? { email: values.email } : {}),
    }

    try {
      const created = await createPatient.mutateAsync(payload)
      toast.success(`Registered ${created.full_name} (${created.mrn})`)
      reset()
      setOpen(false)
    } catch (err) {
      // Surface backend field errors on the matching inputs; fall back to a toast.
      if (err instanceof ApiError && Array.isArray(err.details)) {
        const fieldErrors = err.details as Array<{ field?: string; message?: string }>
        let mapped = false
        for (const fe of fieldErrors) {
          if (fe.field && fe.field in schema.shape) {
            setError(fe.field as Path<FormValues>, { message: fe.message ?? 'Invalid value' })
            mapped = true
          }
        }
        if (!mapped) toast.error(err.message)
      } else {
        toast.error(err instanceof ApiError ? err.message : 'Could not register the patient.')
      }
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) reset()
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Register patient</DialogTitle>
          <DialogDescription>Create a new patient record for this hospital.</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="grid grid-cols-2 gap-4">
            <Field label="First name" required error={errors.first_name?.message}>
              {(p) => <Input placeholder="Ananya" {...p} {...register('first_name')} />}
            </Field>
            <Field label="Last name" required error={errors.last_name?.message}>
              {(p) => <Input placeholder="Rao" {...p} {...register('last_name')} />}
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Date of birth" required error={errors.date_of_birth?.message}>
              {(p) => <Input type="date" {...p} {...register('date_of_birth')} />}
            </Field>
            <Controller
              control={control}
              name="gender"
              render={({ field }) => (
                <Field label="Gender" required error={errors.gender?.message}>
                  {(p) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id={p.id} aria-invalid={p['aria-invalid']}>
                        <SelectValue placeholder="Select" />
                      </SelectTrigger>
                      <SelectContent>
                        {GENDERS.map((g) => (
                          <SelectItem key={g.value} value={g.value}>
                            {g.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </Field>
              )}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Phone" hint="E.164, e.g. +919812345678" error={errors.phone?.message}>
              {(p) => <Input placeholder="+91…" {...p} {...register('phone')} />}
            </Field>
            <Controller
              control={control}
              name="blood_group"
              render={({ field }) => (
                <Field label="Blood group" error={errors.blood_group?.message}>
                  {(p) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id={p.id} aria-invalid={p['aria-invalid']}>
                        <SelectValue placeholder="Optional" />
                      </SelectTrigger>
                      <SelectContent>
                        {BLOOD_GROUPS.map((b) => (
                          <SelectItem key={b} value={b}>
                            {b}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </Field>
              )}
            />
          </div>

          <Field label="Email" error={errors.email?.message}>
            {(p) => <Input type="email" placeholder="ananya@example.com" {...p} {...register('email')} />}
          </Field>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createPatient.isPending}>
              {createPatient.isPending && <Loader2 className="size-4 animate-spin" />}
              Register
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
