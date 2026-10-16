import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

/**
 * One labelled fact in a `<dl>` card, with an icon beside the label.
 *
 * A `<div>` inside a `<dl>` may hold only `<dt>` and `<dd>`, so the icon sits
 * inside the `<dt>` and the value is indented to line up with the label text.
 */
export function DetailRow({ icon: Icon, label, children }: { icon: LucideIcon; label: string; children: ReactNode }) {
  return (
    <div className="p-4">
      <dt className="text-body-sm text-on-surface-variant flex items-start gap-3">
        <Icon className="text-secondary mt-0.5 size-5 shrink-0" aria-hidden />
        {label}
      </dt>
      <dd className="text-body-lg text-on-surface pl-8 break-words">{children}</dd>
    </div>
  )
}
