import type { ComponentProps } from 'react'
import { Accordion as AccordionPrimitive } from 'radix-ui'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

const Accordion = AccordionPrimitive.Root

function AccordionItem({ className, ...props }: ComponentProps<typeof AccordionPrimitive.Item>) {
  return (
    <AccordionPrimitive.Item
      className={cn('neo-extruded bg-surface overflow-hidden rounded-2xl', className)}
      {...props}
    />
  )
}

function AccordionTrigger({
  className,
  children,
  ...props
}: ComponentProps<typeof AccordionPrimitive.Trigger>) {
  return (
    <AccordionPrimitive.Header className="flex">
      <AccordionPrimitive.Trigger
        className={cn(
          'group font-display text-title-lg text-primary flex flex-1 items-center justify-between gap-4 px-6 py-5 text-left font-bold outline-none transition-colors',
          'hover:text-secondary focus-visible:ring-2 focus-visible:ring-secondary',
          className,
        )}
        {...props}
      >
        {children}
        <ChevronDown className="text-outline size-5 shrink-0 transition-transform duration-300 group-data-[state=open]:rotate-180" />
      </AccordionPrimitive.Trigger>
    </AccordionPrimitive.Header>
  )
}

function AccordionContent({
  className,
  children,
  ...props
}: ComponentProps<typeof AccordionPrimitive.Content>) {
  return (
    <AccordionPrimitive.Content
      className={cn(
        'data-[state=open]:animate-accordion-down data-[state=closed]:animate-accordion-up overflow-hidden',
        className,
      )}
      {...props}
    >
      <div className="font-body text-body-md text-on-surface-variant px-6 pb-5">{children}</div>
    </AccordionPrimitive.Content>
  )
}

export { Accordion, AccordionItem, AccordionTrigger, AccordionContent }
