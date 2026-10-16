import { type ReactNode, useId } from 'react'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

interface FieldProps {
  label: string
  /** Validation error message; when present the field renders in the error state. */
  error?: string
  /** Optional helper text shown below the control (hidden when an error is shown). */
  hint?: string
  required?: boolean
  className?: string
  /**
   * Render-prop that receives the ids to wire onto the control:
   * `id`, `aria-invalid`, and `aria-describedby`.
   */
  children: (props: {
    id: string
    'aria-invalid': boolean
    'aria-describedby': string | undefined
  }) => ReactNode
}

/**
 * Form-field wrapper enforcing the label + error slot + help-text slot contract
 * (frontend/CLAUDE.md). Generates and wires the a11y ids for the control.
 */
export function Field({ label, error, hint, required, className, children }: FieldProps) {
  const id = useId()
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined

  return (
    <div className={cn('space-y-2', className)}>
      <Label htmlFor={id}>
        {label}
        {required && <span className="text-error">*</span>}
      </Label>
      {children({ id, 'aria-invalid': !!error, 'aria-describedby': describedBy })}
      {error ? (
        <p id={`${id}-error`} className="font-body text-error text-xs" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="font-body text-outline text-xs">
          {hint}
        </p>
      ) : null}
    </div>
  )
}
