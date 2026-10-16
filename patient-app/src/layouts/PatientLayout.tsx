import { CalendarDays, CircleUserRound, Hospital, House, type LucideIcon } from 'lucide-react'
import { Link, matchPath, Outlet, useLocation } from 'react-router-dom'
import { cn } from '@atheris/ui'
import { Brand } from '@/components/Brand'

/**
 * `current`: the paths on which the entry is the current page. Hospitals and
 * Appointments stay current on the pages under them; Account also covers
 * linking a hospital record, which is reached from it.
 */
const NAV: { to: string; label: string; icon: LucideIcon; current: string[] }[] = [
  { to: '/', label: 'Home', icon: House, current: ['/'] },
  { to: '/hospitals', label: 'Hospitals', icon: Hospital, current: ['/hospitals/*'] },
  { to: '/appointments', label: 'Appointments', icon: CalendarDays, current: ['/appointments/*'] },
  { to: '/account', label: 'Account', icon: CircleUserRound, current: ['/account', '/link-patient'] },
]

/**
 * Mobile-first shell for the signed-in app: a quiet header, one column of
 * content, and navigation within thumb reach at the bottom. On wider screens
 * the same navigation moves up into the header row and the column widens.
 *
 * It is one `<nav>` either way, so assistive technology meets one main
 * navigation whatever the screen size.
 */
export function PatientLayout() {
  const { pathname } = useLocation()

  return (
    <div className="bg-background flex min-h-dvh flex-col">
      <header className="bg-background/95 sticky top-0 z-10 border-b">
        <div className="mx-auto flex h-14 w-full max-w-xl items-center px-4 md:max-w-3xl">
          <Brand />
        </div>
      </header>

      <main className="mx-auto w-full max-w-xl flex-1 px-4 pt-6 pb-28 md:max-w-3xl md:pt-10 md:pb-16">
        <Outlet />
      </main>

      <nav
        aria-label="Main"
        className={cn(
          'bg-surface-container-lowest fixed inset-x-0 bottom-0 z-20 border-t pb-[env(safe-area-inset-bottom)]',
          // Wide screens: laid over the right of the header row, leaving the brand clickable.
          'md:pointer-events-none md:bottom-auto md:top-0 md:border-t-0 md:bg-transparent md:pb-0',
        )}
      >
        <ul className="mx-auto flex w-full max-w-xl md:h-14 md:max-w-3xl md:justify-end md:gap-1 md:px-4">
          {NAV.map(({ to, label, icon: Icon, current }) => {
            const isCurrent = current.some((path) => matchPath(path, pathname) !== null)
            return (
              <li key={to} className="flex-1 md:pointer-events-auto md:flex md:flex-none md:items-center">
                <Link
                  to={to}
                  aria-current={isCurrent ? 'page' : undefined}
                  className={cn(
                    'text-body-sm flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 text-center leading-tight font-medium whitespace-nowrap',
                    'md:min-h-11 md:flex-row md:gap-2 md:rounded-xl md:px-3',
                    'focus-visible:ring-ring/50 outline-none focus-visible:ring-[3px]',
                    isCurrent
                      ? 'text-secondary md:bg-secondary-fixed/50'
                      : 'text-on-surface-variant hover:text-on-surface md:hover:bg-surface-container',
                  )}
                >
                  <Icon className="size-5" aria-hidden />
                  {label}
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>
    </div>
  )
}
