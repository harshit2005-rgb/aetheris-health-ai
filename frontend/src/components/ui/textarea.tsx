import type { ComponentProps } from 'react'
import { controlClass } from '@/components/ui/control'
import { cn } from '@/lib/utils'

function Textarea({ className, ...props }: ComponentProps<'textarea'>) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(controlClass, 'min-h-20 resize-y', className)}
      {...props}
    />
  )
}

export { Textarea }
