import { type ReactNode, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
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
import { useCreatePatient } from '@/api/patients'

const DEPARTMENTS = ['Cardiology', 'Pulmonology', 'Endocrinology', 'Surgery', 'Neurology', 'General']

const schema = z.object({
  name: z.string().min(2, 'Name is required'),
  age: z.coerce.number().int().min(0, 'Enter a valid age').max(130, 'Enter a valid age'),
  gender: z.enum(['M', 'F'], { message: 'Select a gender' }),
  phone: z.string().min(7, 'Enter a valid phone number'),
  department: z.string().min(1, 'Select a department'),
})

type FormValues = z.input<typeof schema>

/** Reference create flow: Dialog + form kit + RHF/Zod + a typed mutation hook. */
export function RegisterPatientDialog({ trigger }: { trigger: ReactNode }) {
  const [open, setOpen] = useState(false)
  const createPatient = useCreatePatient()

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', age: '' as unknown as number, phone: '', department: '' },
  })

  async function onSubmit(values: FormValues) {
    try {
      const parsed = schema.parse(values)
      await createPatient.mutateAsync(parsed)
      toast.success(`Registered ${parsed.name}`)
      reset()
      setOpen(false)
    } catch {
      toast.error('Could not register the patient. Please try again.')
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
          <Field label="Full name" required error={errors.name?.message}>
            {(p) => <Input placeholder="e.g. Ravi Menon" {...p} {...register('name')} />}
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Age" required error={errors.age?.message}>
              {(p) => <Input type="number" min={0} placeholder="45" {...p} {...register('age')} />}
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
                        <SelectItem value="M">Male</SelectItem>
                        <SelectItem value="F">Female</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                </Field>
              )}
            />
          </div>

          <Field label="Phone" required error={errors.phone?.message}>
            {(p) => <Input placeholder="+91 98847 21908" {...p} {...register('phone')} />}
          </Field>

          <Controller
            control={control}
            name="department"
            render={({ field }) => (
              <Field label="Department" required error={errors.department?.message}>
                {(p) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id={p.id} aria-invalid={p['aria-invalid']}>
                      <SelectValue placeholder="Select a department" />
                    </SelectTrigger>
                    <SelectContent>
                      {DEPARTMENTS.map((d) => (
                        <SelectItem key={d} value={d}>
                          {d}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </Field>
            )}
          />

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
