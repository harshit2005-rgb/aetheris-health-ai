import { Menu, Search, Bell, Sparkles } from 'lucide-react'
import Breadcrumbs from '@/components/layout/Breadcrumbs'
import { useAuthStore } from '@/store/auth-store'
import { ROLE_LABELS } from '@/lib/rbac'

function initials(name: string) {
  const parts = name.trim().split(/\s+/)
  return parts.slice(-2).map((p) => p[0]).join('').toUpperCase()
}

interface TopBarProps {
  onOpenSidebar: () => void
  onOpenCopilot: () => void
}

/** App top bar: search, notifications, AI Copilot, user menu (spec 2C §2, §6). */
export default function TopBar({ onOpenSidebar, onOpenCopilot }: TopBarProps) {
  const user = useAuthStore((s) => s.user)
  const name = user?.name ?? 'User'
  const roleLabel = user?.role ? ROLE_LABELS[user.role] : ''

  return (
    <header className="glassmorphism shadow-glass-panel sticky top-0 z-30 flex h-16 items-center gap-3 rounded-2xl px-3 md:px-4">
      {/* Mobile menu */}
      <button
        onClick={onOpenSidebar}
        aria-label="Open menu"
        className="text-primary hover:bg-white/30 flex size-10 items-center justify-center rounded-lg lg:hidden"
      >
        <Menu className="size-5" />
      </button>

      {/* Breadcrumbs (desktop) */}
      <div className="hidden md:block">
        <Breadcrumbs />
      </div>

      {/* Global search */}
      <div className="relative mx-auto w-full max-w-md">
        <Search className="text-outline pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
        <input
          type="text"
          placeholder="Search patients, doctors, invoices..."
          className="neo-pressed bg-surface/60 font-body text-body-sm placeholder:text-outline-variant focus:ring-secondary w-full rounded-full py-2.5 pr-16 pl-9 outline-none focus:ring-2"
        />
        <kbd className="font-label text-outline border-outline-variant/50 bg-surface/80 pointer-events-none absolute top-1/2 right-2.5 hidden -translate-y-1/2 rounded border px-1.5 py-0.5 text-[10px] sm:block">
          ⌘K
        </kbd>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5">
        <button
          aria-label="Notifications"
          className="text-on-surface-variant hover:bg-white/30 relative flex size-10 items-center justify-center rounded-lg transition-colors"
        >
          <Bell className="size-5" />
          <span className="bg-error absolute top-2 right-2.5 size-2 rounded-full" />
        </button>

        <button
          onClick={onOpenCopilot}
          aria-label="AI Copilot"
          className="text-secondary hover:bg-white/30 hidden size-10 items-center justify-center rounded-lg transition-colors sm:flex"
        >
          <Sparkles className="size-5" />
        </button>

        <button className="hover:bg-white/30 flex items-center gap-2 rounded-full py-1 pr-1 pl-2 transition-colors">
          <div className="hidden text-right leading-tight md:block">
            <p className="font-body text-body-sm text-primary font-bold">{name}</p>
            <p className="font-body text-outline text-[11px]">{roleLabel}</p>
          </div>
          <span className="neo-extruded bg-primary-container flex size-9 items-center justify-center rounded-full text-xs font-bold text-white">
            {initials(name)}
          </span>
        </button>
      </div>
    </header>
  )
}
