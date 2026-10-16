import type { ComponentProps } from 'react'
import { Tabs as TabsPrimitive } from 'radix-ui'
import { cn } from '@/lib/utils'

const Tabs = TabsPrimitive.Root

function TabsList({ className, ...props }: ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn(
        'neo-pressed bg-surface inline-flex items-center gap-1 rounded-xl p-1',
        className,
      )}
      {...props}
    />
  )
}

function TabsTrigger({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        'font-label text-label-caps text-on-surface-variant inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 whitespace-nowrap outline-none transition-all',
        'focus-visible:ring-2 focus-visible:ring-secondary',
        'data-[state=active]:neo-extruded data-[state=active]:bg-surface data-[state=active]:text-secondary data-[state=active]:font-bold',
        'disabled:pointer-events-none disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

function TabsContent({ className, ...props }: ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      className={cn('mt-4 outline-none focus-visible:ring-2 focus-visible:ring-secondary', className)}
      {...props}
    />
  )
}

export { Tabs, TabsList, TabsTrigger, TabsContent }
