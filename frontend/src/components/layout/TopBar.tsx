import { Menu, Search, Bell, Sparkles } from 'lucide-react'
import Breadcrumbs from '@/components/layout/Breadcrumbs'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
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

      {/* Global search — not wired yet; disabled so it doesn't read as broken (F10) */}
      <div className="relative mx-auto w-full max-w-md">
        <Search className="text-outline pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
        <input
          type="text"
          disabled
          title="Global search — coming soon"
          placeholder="Search (coming soon)"
          className="neo-pressed bg-surface/60 font-body text-body-sm placeholder:text-outline-variant w-full cursor-not-allowed rounded-full py-2.5 pr-4 pl-9 opacity-60 outline-none"
        />
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5">
        <ThemeToggle />

        {/* Notifications — no data source yet; disabled, no unread dot (F10) */}
        <button
          type="button"
          disabled
          aria-label="Notifications (coming soon)"
          title="Notifications — coming soon"
          className="text-outline-variant flex size-10 cursor-not-allowed items-center justify-center rounded-lg opacity-60"
        >
          <Bell className="size-5" />
        </button>

        <button
          type="button"
          onClick={onOpenCopilot}
          aria-label="AI Copilot"
          className="text-secondary hover:bg-white/30 hidden size-10 items-center justify-center rounded-lg transition-colors sm:flex"
        >
          <Sparkles className="size-5" />
        </button>

        {/* User identity — display only; logout lives in the sidebar (F10) */}
        <div className="flex items-center gap-2 py-1 pr-1 pl-2">
          <div className="hidden text-right leading-tight md:block">
            <p className="font-body text-body-sm text-primary font-bold">{name}</p>
            <p className="font-body text-outline text-[11px]">{roleLabel}</p>
          </div>
          <span className="neo-extruded bg-primary-container flex size-9 items-center justify-center rounded-full text-xs font-bold text-white">
            {initials(name)}
          </span>
        </div>
      </div>
    </header>
  )
}
