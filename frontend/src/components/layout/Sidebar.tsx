import { useEffect } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { ChevronsLeft, ChevronsRight, LogOut, Sparkles } from 'lucide-react'
import { Logo } from '@/components/brand/Logo'
import { useAuthStore } from '@/store/auth-store'
import { usePermissions } from '@/hooks/usePermissions'
import { ROLE_LABELS } from '@/lib/rbac'
import { cn } from '@/lib/utils'

function initials(name: string) {
  const parts = name.trim().split(/\s+/)
  return parts.slice(-2).map((p) => p[0]).join('').toUpperCase()
}

interface SidebarProps {
  collapsed: boolean
  onToggleCollapse: () => void
  mobileOpen: boolean
  onMobileClose: () => void
  onOpenCopilot: () => void
}

export default function Sidebar({
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onMobileClose,
  onOpenCopilot,
}: SidebarProps) {
  const navigate = useNavigate()
  const { nav, role } = usePermissions()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  const name = user?.name ?? 'User'
  const roleLabel = role ? ROLE_LABELS[role] : ''

  // Close the mobile drawer on Escape (F11).
  useEffect(() => {
    if (!mobileOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onMobileClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mobileOpen, onMobileClose])

  function handleLogout() {
    logout()
    toast.success('Signed out')
    navigate('/login', { replace: true })
  }

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <button
          aria-label="Close menu"
          onClick={onMobileClose}
          className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm lg:hidden"
        />
      )}

      <aside
        className={cn(
          'neo-extruded bg-background fixed z-50 flex h-dvh flex-col gap-2 p-4 transition-all duration-300',
          'top-0 bottom-0 left-0',
          collapsed ? 'w-20' : 'w-64',
          mobileOpen ? 'translate-x-0' : '-translate-x-[110%] lg:translate-x-0',
        )}
      >
        {/* Brand */}
        <div className="mb-4 flex items-center justify-between px-1 pt-1">
          <Link to="/dashboard" className="flex items-center overflow-hidden" onClick={onMobileClose}>
            <Logo variant={collapsed ? 'mark' : 'lockup'} className={collapsed ? 'h-9' : 'h-10'} />
          </Link>
          <button
            onClick={onToggleCollapse}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="text-outline hover:text-primary hidden rounded-lg p-1 transition-colors lg:block"
          >
            {collapsed ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-1 overflow-y-auto">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onMobileClose}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-xl px-3 py-2.5 transition-all duration-200',
                  collapsed && 'justify-center',
                  isActive
                    ? 'neo-pressed text-secondary font-bold'
                    : 'text-on-surface-variant hover:text-primary hover:translate-x-0.5',
                )
              }
              title={collapsed ? label : undefined}
            >
              <Icon className="size-5 shrink-0" />
              {!collapsed && <span className="font-body text-body-md truncate">{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* AI Copilot launcher */}
        <button
          onClick={onOpenCopilot}
          className={cn(
            'shadow-neo-base bg-primary-container text-on-primary flex items-center gap-3 rounded-xl px-3 py-2.5 font-bold transition-transform active:scale-[0.98]',
            collapsed && 'justify-center',
          )}
          title="AI Copilot"
        >
          <Sparkles className="text-secondary-container size-5 shrink-0" />
          {!collapsed && <span className="font-label text-label-caps">AI Copilot</span>}
        </button>

        {/* User */}
        <div className="border-outline-variant/30 mt-2 flex items-center gap-3 border-t pt-3">
          <span className="neo-extruded bg-primary-container flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white">
            {initials(name)}
          </span>
          {!collapsed && (
            <>
              <div className="min-w-0 flex-1">
                <p className="font-body text-body-sm text-primary truncate font-bold">{name}</p>
                <p className="font-body text-outline truncate text-xs">{roleLabel}</p>
              </div>
              <button
                onClick={handleLogout}
                aria-label="Sign out"
                title="Sign out"
                className="text-outline-variant hover:text-error transition-colors active:scale-90"
              >
                <LogOut className="size-5" />
              </button>
            </>
          )}
        </div>
      </aside>
    </>
  )
}
