import { type ReactNode, useRef, useState } from 'react'
import {
  FormProvider,
  useForm,
  type DefaultValues,
  type FieldValues,
  type Path,
  type Resolver,
  type UseFormReturn,
} from 'react-hook-form'
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
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { ApiError } from '@/api/types'
import { billingErrorMessage, splitFieldErrors } from './billing'

interface InvoiceFormDialogProps<T extends FieldValues> {
  trigger: ReactNode
  title: string
  description: ReactNode
  resolver: Resolver<T>
  /** Read each time the dialog opens, so it always starts from the invoice's current figures. */
  defaults: () => DefaultValues<T>
  submitLabel: string
  pendingLabel: string
  /** Style the confirm button as destructive (void, refund). */
  destructive?: boolean
  /** Label for the button that closes without acting. */
  dismissLabel?: string
  /** Shown when the failure is not one the API explains (5xx, network). */
  fallbackError: string
  /** Send the request. Resolves to the success toast. */
  onSubmit: (values: T) => Promise<string>
  children: (form: UseFormReturn<T>) => ReactNode
}

/**
 * The dialog behind every invoice action that needs input or confirmation:
 * payment, refund, discount, issue, void.
 *
 * It owns what those share. The form resets to the invoice's current values on
 * open; a second submit is ignored while one is in flight; a 422 lands under
 * the field it names; and any other refusal from the API — overpayment, wrong
 * status, cash-only — is shown in the dialog in the API's own words, so the
 * user can correct and retry.
 */
export function InvoiceFormDialog<T extends FieldValues>({
  trigger,
  title,
  description,
  resolver,
  defaults,
  submitLabel,
  pendingLabel,
  destructive,
  dismissLabel = 'Cancel',
  fallbackError,
  onSubmit,
  children,
}: InvoiceFormDialogProps<T>) {
  const [open, setOpen] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const submitting = useRef(false)
  const form = useForm<T>({ resolver, defaultValues: defaults() })

  function onOpenChange(next: boolean) {
    setOpen(next)
    setNotice(null)
    if (next) form.reset(defaults())
  }

  async function submit(values: T) {
    if (submitting.current) return
    submitting.current = true
    setPending(true)
    setNotice(null)
    try {
      toast.success(await onSubmit(values))
      setOpen(false)
    } catch (err) {
      const { onFields, other } = splitFieldErrors(err, (field) => field in form.getValues())
      for (const fe of onFields) form.setError(fe.field as Path<T>, { message: fe.message })
      if (onFields.length === 0 || other.length > 0) {
        const message = other.length > 0 ? other.join(' ') : billingErrorMessage(err, fallbackError)
        setNotice(message)
        // The invoice is refetched after these, and may no longer offer this
        // action at all — in which case this dialog goes with it. The toast
        // makes sure the reason is still seen.
        if (err instanceof ApiError && [400, 404, 409].includes(err.status ?? 0)) toast.error(message)
      }
    } finally {
      submitting.current = false
      setPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <FormProvider {...form}>
          <form onSubmit={(e) => form.handleSubmit(submit)(e)} className="space-y-4" noValidate>
            {notice && (
              <Alert variant="error" title="That didn't go through">
                {notice}
              </Alert>
            )}
            {children(form)}
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
                {dismissLabel}
              </Button>
              <Button
                type="submit"
                variant={destructive ? 'destructive' : 'default'}
                disabled={pending}
                aria-busy={pending}
              >
                {pending && <Loader2 className="size-4 animate-spin" />}
                {pending ? pendingLabel : submitLabel}
              </Button>
            </DialogFooter>
          </form>
        </FormProvider>
      </DialogContent>
    </Dialog>
  )
}
