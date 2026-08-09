import { useEffect } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Icon } from '@/components/ui/icon'
import { Logo } from '@/components/brand/Logo'
import { useAuthStore } from '@/store/auth-store'
import { cn } from '@/lib/utils'

function initials(name: string) {
  // Use the last two name tokens so honorifics ("Dr.") don't dominate.
  const parts = name.trim().split(/\s+/)
  return parts
    .slice(-2)
    .map((p) => p[0])
    .join('')
    .toUpperCase()
}

const VIEW_NAV = [
  { to: '/dashboard', label: 'Overview', icon: 'grid_view' },
  { to: '/diagnostics', label: 'Diagnostics', icon: 'clinical_notes' },
  { to: '/records', label: 'Records', icon: 'folder_shared' },
]

// Placeholder destinations — not yet routed, so rendered as inert items.
const MANAGE_NAV = [
  { label: 'Messages', icon: 'chat' },
  { label: 'History', icon: 'history' },
]

function NavItem({ to, label, icon, onClick }: { to: string; label: string; icon: string; onClick: () => void }) {
  return (
    <NavLink
      to={to}
      end
      onClick={onClick}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-lg px-4 py-3 transition-all duration-200',
          isActive
            ? 'neo-pressed text-secondary font-bold'
            : 'text-on-surface-variant hover:text-primary hover:translate-x-1',
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon name={icon} filled={isActive} />
          <span className="font-body text-body-md">{label}</span>
        </>
      )}
    </NavLink>
  )
}

interface AppSidebarProps {
  open: boolean
  onClose: () => void
}

export default function AppSidebar({ open, onClose }: AppSidebarProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  const name = user?.name ?? 'Dr. A. Chen'
  const role = user?.role ? user.role[0].toUpperCase() + user.role.slice(1) : 'Neurology Dept.'

  // Close the mobile drawer whenever the route changes.
  useEffect(() => {
    onClose()
  }, [location.pathname]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleLogout() {
    logout()
    toast.success('Signed out')
    navigate('/login', { replace: true })
  }

  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <button
          aria-label="Close menu"
          onClick={onClose}
          className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm md:hidden"
        />
      )}

      <aside
        className={cn(
          'neo-extruded bg-background fixed z-50 flex w-72 flex-col gap-2 rounded-r-2xl p-6 transition-transform duration-300',
          'top-0 bottom-0 left-0',
          'md:top-6 md:bottom-6 md:left-6 md:z-40 md:translate-x-0 md:rounded-2xl',
          open ? 'translate-x-0' : '-translate-x-[110%] md:translate-x-0',
        )}
      >
        {/* Brand */}
        <Link to="/" className="mb-8 flex items-center pt-2 pl-2">
          <Logo className="h-12 md:h-14" />
        </Link>

        {/* Search */}
        <div className="neo-pressed bg-surface mb-6 flex items-center gap-2 rounded-full px-4 py-2.5">
          <input
            type="text"
            placeholder="Search tasks..."
            className="text-body-sm placeholder:text-outline w-full border-none bg-transparent outline-none"
          />
          <Icon name="search" className="text-outline" />
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto pr-1">
          <p className="font-label text-label-caps text-outline-variant mb-3 px-4">View</p>
          <ul className="space-y-2">
            {VIEW_NAV.map((item) => (
              <li key={item.label}>
                <NavItem {...item} onClick={onClose} />
              </li>
            ))}
          </ul>

          <p className="font-label text-label-caps text-outline-variant mt-8 mb-3 px-4">Manage</p>
          <ul className="space-y-2">
            {MANAGE_NAV.map((item) => (
              <li key={item.label}>
                <button
                  type="button"
                  className="text-on-surface-variant hover:text-primary flex w-full items-center gap-3 rounded-lg px-4 py-3 transition-all duration-200 hover:translate-x-1"
                >
                  <Icon name={item.icon} />
                  <span className="font-body text-body-md">{item.label}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* User */}
        <div className="mt-auto flex items-center gap-3 pt-4">
          <span className="neo-extruded bg-primary-container flex h-11 w-11 items-center justify-center rounded-full text-sm font-bold text-white">
            {initials(name)}
          </span>
          <div className="min-w-0">
            <p className="font-body text-body-sm text-primary truncate font-bold">{name}</p>
            <p className="font-body text-outline truncate text-xs">{role}</p>
          </div>
          <button
            onClick={handleLogout}
            aria-label="Sign out"
            title="Sign out"
            className="text-outline-variant hover:text-error ml-auto transition-colors active:scale-90"
          >
            <Icon name="logout" />
          </button>
        </div>
      </aside>
    </>
  )
}
