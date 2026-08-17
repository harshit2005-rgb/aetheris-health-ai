import type { LucideIcon } from 'lucide-react'
import { Check } from 'lucide-react'
import PageHeader from '@/components/layout/PageHeader'

interface ScaffoldPageProps {
  title: string
  subtitle: string
  icon: LucideIcon
  /** Planned capabilities for this module (from the spec), shown as a checklist. */
  planned: string[]
  specRef: string
}

/** Placeholder for modules that are planned but not yet built (Phase 0). */
export default function ScaffoldPage({
  title,
  subtitle,
  icon: Icon,
  planned,
  specRef,
}: ScaffoldPageProps) {
  return (
    <div className="w-full">
      <PageHeader title={title} subtitle={subtitle} />

      <div className="neo-extruded bg-surface rounded-2xl p-8 md:p-12">
        <div className="flex flex-col items-center text-center">
          <span className="bg-secondary/10 text-secondary mb-5 flex size-16 items-center justify-center rounded-2xl">
            <Icon className="size-8" />
          </span>
          <h2 className="font-display text-headline-md text-primary font-bold">
            This module is on the roadmap
          </h2>
          <p className="font-body text-body-md text-on-surface-variant mt-2 max-w-md">
            The {title} module is scaffolded and routed. Here is what it will include, per{' '}
            {specRef}.
          </p>
        </div>

        <ul className="mx-auto mt-8 grid max-w-2xl gap-3 sm:grid-cols-2">
          {planned.map((item) => (
            <li
              key={item}
              className="neo-pressed bg-surface font-body text-body-sm text-on-surface flex items-center gap-2 rounded-xl px-4 py-3"
            >
              <Check className="text-secondary size-4 shrink-0" />
              {item}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
