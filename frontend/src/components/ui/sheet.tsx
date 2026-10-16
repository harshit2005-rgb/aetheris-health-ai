import type { ComponentProps } from 'react'
import { Dialog as SheetPrimitive } from 'radix-ui'
import { cn } from '@/lib/utils'

/**
 * Side-panel primitive built on Radix Dialog. Gives a real focus trap,
 * Escape-to-close, scroll lock, and `inert`/`aria-hidden` on the rest of the
 * page for free — the accessible foundation for the app's overlays.
 */
const Sheet = SheetPrimitive.Root
const SheetTrigger = SheetPrimitive.Trigger
const SheetClose = SheetPrimitive.Close
const SheetTitle = SheetPrimitive.Title
const SheetDescription = SheetPrimitive.Description

function SheetOverlay({ className, ...props }: ComponentProps<typeof SheetPrimitive.Overlay>) {
  return (
    <SheetPrimitive.Overlay
      className={cn(
        'fixed inset-0 z-50 bg-black/30 backdrop-blur-sm',
        'data-[state=open]:animate-in data-[state=closed]:animate-out',
        'data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0',
        className,
      )}
      {...props}
    />
  )
}

const SIDE = {
  left: 'inset-y-0 left-0 h-dvh data-[state=open]:slide-in-from-left data-[state=closed]:slide-out-to-left',
  right:
    'inset-y-0 right-0 h-dvh data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right',
} as const

interface SheetContentProps extends ComponentProps<typeof SheetPrimitive.Content> {
  side?: keyof typeof SIDE
}

function SheetContent({ side = 'right', className, children, ...props }: SheetContentProps) {
  return (
    <SheetPrimitive.Portal>
      <SheetOverlay />
      <SheetPrimitive.Content
        className={cn(
          'fixed z-50 flex flex-col shadow-2xl outline-none',
          'data-[state=open]:animate-in data-[state=closed]:animate-out',
          'data-[state=closed]:duration-300 data-[state=open]:duration-300',
          SIDE[side],
          className,
        )}
        {...props}
      >
        {children}
      </SheetPrimitive.Content>
    </SheetPrimitive.Portal>
  )
}

export { Sheet, SheetTrigger, SheetClose, SheetContent, SheetOverlay, SheetTitle, SheetDescription }
