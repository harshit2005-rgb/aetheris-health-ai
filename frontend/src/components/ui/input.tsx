import type { ComponentProps } from 'react'
import { controlClass } from '@/components/ui/control'
import { cn } from '@/lib/utils'

function Input({ className, type, ...props }: ComponentProps<'input'>) {
  return <input type={type} data-slot="input" className={cn(controlClass, className)} {...props} />
}

export { Input }
