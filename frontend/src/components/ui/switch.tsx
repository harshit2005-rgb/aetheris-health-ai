import type { ComponentProps } from 'react'
import { Switch as SwitchPrimitive } from 'radix-ui'
import { cn } from '@/lib/utils'

function Switch({ className, ...props }: ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      className={cn(
        'peer inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full p-0.5 outline-none transition-colors',
        'focus-visible:ring-2 focus-visible:ring-secondary focus-visible:ring-offset-2',
        'data-[state=unchecked]:bg-surface-container-highest data-[state=checked]:bg-secondary-container',
        'disabled:cursor-not-allowed disabled:opacity-60',
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        className={cn(
          'pointer-events-none block size-5 rounded-full bg-white shadow-sm transition-transform',
          'data-[state=unchecked]:translate-x-0 data-[state=checked]:translate-x-5',
        )}
      />
    </SwitchPrimitive.Root>
  )
}

export { Switch }
