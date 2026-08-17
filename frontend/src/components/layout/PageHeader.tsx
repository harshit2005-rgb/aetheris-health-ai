import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  subtitle?: string
  /** Primary/secondary actions, rendered top-right (spec: primary action top-right). */
  actions?: ReactNode
}

/** Standard module page header: title + subtitle + top-right actions (spec Part 1, 12). */
export default function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
      <div>
        <h1 className="font-display text-primary text-3xl font-extrabold tracking-tight">{title}</h1>
        {subtitle && (
          <p className="font-body text-body-md text-on-surface-variant mt-1">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </div>
  )
}
