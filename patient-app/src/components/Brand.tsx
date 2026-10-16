import { cn } from '@atheris/ui'

/**
 * The product mark and name.
 *
 * The mark is our own artwork (`public/logo-mark.png`), drawn as a background
 * so that it is not an image element: the only `<img>` this app ever renders
 * is a hospital's logo, and that is what the logo-safety tests count.
 */
export function Brand({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <span aria-hidden className="size-9 shrink-0 bg-[url('/logo-mark.png')] bg-contain bg-center bg-no-repeat" />
      <span className="font-display text-primary text-lg font-bold tracking-tight">Atheris Health</span>
    </div>
  )
}
