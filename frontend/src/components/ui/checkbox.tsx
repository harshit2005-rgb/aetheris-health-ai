import type { ComponentProps } from 'react'
import { Checkbox as CheckboxPrimitive } from 'radix-ui'
import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

function Checkbox({ className, ...props }: ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      className={cn(
        'neo-pressed bg-surface peer size-5 shrink-0 rounded-md outline-none transition-shadow',
        'focus-visible:ring-2 focus-visible:ring-secondary',
        'data-[state=checked]:bg-secondary-container data-[state=checked]:shadow-none',
        'disabled:cursor-not-allowed disabled:opacity-60',
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator className="text-on-secondary-container flex items-center justify-center">
        <Check className="size-3.5 stroke-[3]" />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}

export { Checkbox }
