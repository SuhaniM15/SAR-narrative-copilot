import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Briefcase,
  ScrollText,
  LogOut,
  Shield,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/cases', label: 'Cases', icon: Briefcase },
  { to: '/audit', label: 'Audit', icon: ScrollText },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen bg-ink-50">
      <aside className="flex w-64 flex-col border-r border-ink-200 bg-ink-900 text-ink-100">
        <div className="border-b border-ink-800 px-5 py-5">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-brand-100" />
            <div>
              <div className="font-display text-lg font-semibold text-white">
                SAR Copilot
              </div>
              <div className="text-xs text-ink-400">Compliance workbench</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? 'bg-brand-700 text-white'
                    : 'text-ink-300 hover:bg-ink-800 hover:text-white'
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-ink-800 px-4 py-4">
          <div className="mb-3">
            <div className="truncate text-sm font-medium text-white">
              {user?.full_name || user?.email}
            </div>
            <div className="text-xs uppercase tracking-wide text-ink-400">
              {user?.role}
            </div>
          </div>
          <button type="button" onClick={handleLogout} className="btn-secondary w-full">
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="mx-auto max-w-7xl px-6 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
