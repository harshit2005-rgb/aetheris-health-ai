import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from '@/components/layout/Sidebar'
import TopBar from '@/components/layout/TopBar'
import CopilotPanel from '@/components/layout/CopilotPanel'
import { cn } from '@/lib/utils'

/** Authenticated app shell: collapsible sidebar + top bar + AI Copilot (spec 2C, 11). */
export default function DashboardLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [copilotOpen, setCopilotOpen] = useState(false)
  const location = useLocation()

  // Close the mobile drawer on navigation.
  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  return (
    <div className="bg-background min-h-dvh">
      <Sidebar
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((v) => !v)}
        mobileOpen={mobileOpen}
        onMobileClose={() => setMobileOpen(false)}
        onOpenCopilot={() => setCopilotOpen(true)}
      />

      <div className={cn('transition-all duration-300', collapsed ? 'lg:pl-20' : 'lg:pl-64')}>
        <div className="mx-auto max-w-[1600px] p-3 md:p-4">
          <TopBar
            onOpenSidebar={() => setMobileOpen(true)}
            onOpenCopilot={() => setCopilotOpen(true)}
          />
          <main className="py-6">
            <Outlet />
          </main>
        </div>
      </div>

      <CopilotPanel open={copilotOpen} onClose={() => setCopilotOpen(false)} />
    </div>
  )
}
