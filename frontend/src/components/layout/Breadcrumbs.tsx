import { Link, useLocation } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'

const LABELS: Record<string, string> = {
  dashboard: 'Dashboard',
  patients: 'Patients',
  doctors: 'Doctors',
  appointments: 'Appointments',
  billing: 'Billing',
  reports: 'Reports',
  settings: 'Settings',
}

function titleize(seg: string) {
  return LABELS[seg] ?? seg.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

/** Route-derived breadcrumb trail. Spec 2C: breadcrumbs on every page. */
export default function Breadcrumbs() {
  const { pathname } = useLocation()
  const segments = pathname.split('/').filter(Boolean)

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm">
      {segments.map((seg, i) => {
        const to = '/' + segments.slice(0, i + 1).join('/')
        const isLast = i === segments.length - 1
        return (
          <span key={to} className="flex items-center gap-1.5">
            {i > 0 && <ChevronRight className="text-outline-variant size-3.5" />}
            {isLast ? (
              <span className="font-body text-primary font-semibold">{titleize(seg)}</span>
            ) : (
              <Link to={to} className="font-body text-on-surface-variant hover:text-secondary">
                {titleize(seg)}
              </Link>
            )}
          </span>
        )
      })}
    </nav>
  )
}
