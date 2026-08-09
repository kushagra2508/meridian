import { useCallback, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { SideNav } from './SideNav'
import { TopAppBar } from './TopAppBar'

export function AppShell() {
  const [navOpen, setNavOpen] = useState(false)
  const closeNav = useCallback(() => setNavOpen(false), [])

  return (
    <div className="flex min-h-screen bg-background text-on-surface">
      <SideNav open={navOpen} onNavigate={closeNav} />

      <div className="relative flex min-h-screen w-full flex-1 flex-col md:ml-64">
        <TopAppBar onOpenNav={() => setNavOpen(true)} />
        <Outlet />
      </div>
    </div>
  )
}
