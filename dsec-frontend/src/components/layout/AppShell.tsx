// src/components/layout/AppShell.tsx
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import {
  LayoutDashboard, FileText, ClipboardList,
  Settings, Bell, LogOut, Shield,
} from 'lucide-react'
import { cn } from '../../lib/utils'

const navByRole = {
  agent: [
    { to: '/agent', label: '我的案例', icon: FileText },
  ],
  platform_reviewer: [
    { to: '/reviewer', label: '评审任务', icon: ClipboardList },
    { to: '/reviewer/cases', label: '所有案例', icon: FileText },
  ],
  dji_se: [
    { to: '/dji', label: '案例管理', icon: FileText },
    { to: '/dji/disagreements', label: '分歧记录', icon: Shield },
  ],
  admin: [
    { to: '/ops/dashboard', label: '系统概览', icon: LayoutDashboard },
    { to: '/ops/cases', label: '案例管理', icon: FileText },
    { to: '/ops/prompts', label: 'Prompt 管理', icon: Settings },
    { to: '/ops/disagreements', label: '分歧分析', icon: Shield },
    { to: '/ops/audit', label: '审计日志', icon: ClipboardList },
  ],
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuthStore()
  const location = useLocation()
  const navigate = useNavigate()

  const nav = navByRole[user?.role ?? 'agent'] ?? []

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <aside className="w-60 flex-shrink-0 bg-gray-900 text-gray-100 flex flex-col">
        {/* Logo */}
        <div className="flex items-center gap-2 px-5 py-5 border-b border-gray-800">
          <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center font-bold text-white text-sm">D</div>
          <div>
            <div className="text-sm font-semibold leading-tight">DSEC AI</div>
            <div className="text-xs text-gray-400">评审平台</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          {nav.map(({ to, label, icon: Icon }) => {
            const active = location.pathname.startsWith(to)
            return (
              <Link
                key={to}
                to={to}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                  active
                    ? 'bg-brand-600 text-white'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                )}
              >
                <Icon size={16} />
                {label}
              </Link>
            )
          })}
        </nav>

        {/* User */}
        <div className="border-t border-gray-800 px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-brand-500 flex items-center justify-center text-white text-xs font-bold">
              {user?.full_name?.[0] ?? user?.email?.[0]?.toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{user?.full_name ?? user?.email}</div>
              <div className="text-xs text-gray-500">{user?.role}</div>
            </div>
            <button onClick={handleLogout} className="text-gray-500 hover:text-red-400 transition-colors" title="退出">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-end gap-3">
          <button className="btn-ghost p-2 relative">
            <Bell size={18} />
          </button>
        </header>
        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
