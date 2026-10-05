import type { LucideIcon } from 'lucide-react'
import { Hourglass } from 'lucide-react'
import PageHeader from '@/components/layout/PageHeader'

interface ScaffoldPageProps {
  title: string
  subtitle: string
  icon: LucideIcon
  /** Planned capabilities for this module (from the spec), shown as a checklist. */
  planned: string[]
}

/**
 * Page for a module that is planned but not built. It says so plainly and lists
 * what is intended, marked as planned rather than ticked off as done.
 */
export default function ScaffoldPage({
  title,
  subtitle,
  icon: Icon,
  planned,
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
            {title} is not available yet
          </h2>
          <p className="font-body text-body-md text-on-surface-variant mt-2 max-w-md">
            This module is on the roadmap and has no data behind it today. Planned for it:
          </p>
        </div>

        <ul className="mx-auto mt-8 grid max-w-2xl gap-3 sm:grid-cols-2">
          {planned.map((item) => (
            <li
              key={item}
              className="neo-pressed bg-surface font-body text-body-sm text-on-surface flex items-center gap-2 rounded-xl px-4 py-3"
            >
              <Hourglass className="text-outline size-4 shrink-0" aria-hidden />
              {item}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
