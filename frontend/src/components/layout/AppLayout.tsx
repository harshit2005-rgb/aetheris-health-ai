import { useState } from 'react'
import { Link, Outlet } from 'react-router-dom'
import AppSidebar from '@/components/layout/AppSidebar'
import { Logo } from '@/components/brand/Logo'
import { Icon } from '@/components/ui/icon'

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="bg-background flex min-h-screen">
      <AppSidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Mobile top bar */}
      <header className="glassmorphism shadow-glass-panel fixed top-4 right-4 left-4 z-30 flex h-14 items-center justify-between rounded-2xl pr-3 pl-4 md:hidden">
        <Link to="/" className="flex items-center">
          <Logo className="h-8" />
        </Link>
        <button
          type="button"
          onClick={() => setSidebarOpen(true)}
          aria-label="Open menu"
          className="text-primary flex h-10 w-10 items-center justify-center"
        >
          <Icon name="menu" className="text-2xl" />
        </button>
      </header>

      <main className="flex-1 overflow-x-hidden px-4 pt-24 pb-6 md:ml-[336px] md:px-6 md:pt-6">
        <Outlet />
      </main>
    </div>
  )
}
