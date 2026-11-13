import React, { useState } from 'react'
import { Bell, Box, Boxes, LayoutDashboard, Lightbulb, RefreshCw, Search, Users } from 'lucide-react'
import { navigate, routeHref, type Route } from '../../hooks/useHashRoute'

const NAV: { page: Route['page']; label: string; icon: React.ElementType; href: string }[] = [
  { page: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, href: '#/dashboard' },
  { page: 'assets', label: 'Assets', icon: Boxes, href: '#/assets' },
  { page: 'plant', label: '3D Plant', icon: Box, href: '#/plant' },
  { page: 'insights', label: 'AI Insights', icon: Lightbulb, href: '#/insights' },
]

const Logo = () => (
  <div className="flex items-center gap-2.5 px-5 h-16">
    <svg viewBox="0 0 32 32" className="w-8 h-8 text-white" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden>
      <path d="M16 3 28 10v12L16 29 4 22V10z" strokeLinejoin="round" />
      <path d="M4 10l12 7 12-7M16 17v12" strokeLinejoin="round" />
    </svg>
    <div className="leading-tight">
      <div className="text-white font-bold tracking-wide text-[15px]">TWINOPS</div>
      <div className="text-[10px] text-blue-200/80">Digital Twin Platform</div>
    </div>
  </div>
)

export const Sidebar: React.FC<{ active: Route['page'] }> = ({ active }) => {
  const current = active === 'asset' ? 'assets' : active
  const link = (page: Route['page'], label: string, Icon: React.ElementType, href: string) => (
    <a
      key={page}
      href={href}
      aria-current={current === page ? 'page' : undefined}
      className={`flex items-center gap-3 mx-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
        current === page ? 'bg-blue-600 text-white shadow-sm' : 'text-blue-100/80 hover:bg-white/5 hover:text-white'
      }`}
    >
      <Icon className="w-4 h-4" />
      {label}
    </a>
  )
  return (
    <nav className="w-60 shrink-0 bg-[#0b1d4a] flex flex-col" aria-label="Main">
      <Logo />
      <div className="mt-4 flex flex-col gap-1">{NAV.map((n) => link(n.page, n.label, n.icon, n.href))}</div>
      <div className="mx-6 my-5 border-t border-white/10" />
      <div className="flex flex-col gap-1">{link('users', 'Users', Users, '#/users')}</div>
      <div className="mt-auto px-6 py-5 text-[11px] text-blue-200/60">
        Site PUNE-01 · v1.0
      </div>
    </nav>
  )
}

export const Topbar: React.FC<{
  connectionState: 'connected' | 'connecting' | 'disconnected'
  lastLatencyMs: number
  alarmCount: number
  onRefresh: () => void
}> = ({ connectionState, lastLatencyMs, alarmCount, onRefresh }) => {
  const [q, setQ] = useState('')
  const online = connectionState === 'connected'
  return (
    <header className="h-16 shrink-0 flex items-center gap-4 px-6 bg-white/70 backdrop-blur border-b border-slate-200">
      <form
        className="flex-1 max-w-xl"
        role="search"
        onSubmit={(e) => {
          e.preventDefault()
          navigate({ page: 'assets', q: q.trim() })
        }}
      >
        <label className="flex items-center gap-2 rounded-xl bg-slate-100 px-3.5 py-2 text-sm text-slate-500 focus-within:ring-2 focus-within:ring-blue-500/40">
          <Search className="w-4 h-4" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search assets by ID, name, make or serial…"
            aria-label="Search assets"
            className="bg-transparent outline-none w-full text-slate-900 placeholder:text-slate-400"
          />
        </label>
      </form>

      <div className="ml-auto flex items-center gap-3">
        <span
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold ${
            online ? 'bg-emerald-50 text-emerald-700' : connectionState === 'connecting' ? 'bg-amber-50 text-amber-700' : 'bg-rose-50 text-rose-700'
          }`}
          data-testid="connection-state"
        >
          <span className={`w-2 h-2 rounded-full ${online ? 'bg-emerald-500' : connectionState === 'connecting' ? 'bg-amber-500' : 'bg-rose-500'}`} />
          {online ? `Live · ${lastLatencyMs}ms` : connectionState === 'connecting' ? 'Connecting…' : 'Offline'}
        </span>
        <button
          onClick={onRefresh}
          className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900"
          aria-label="Refresh twin snapshot"
          title="Refresh twin snapshot"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
        <a
          href={routeHref({ page: 'insights' })}
          className="relative p-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900"
          aria-label={`Active alarms: ${alarmCount}`}
        >
          <Bell className="w-4 h-4" />
          {alarmCount > 0 && (
            <span
              className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full bg-rose-500 text-white text-[10px] font-bold flex items-center justify-center"
              data-testid="alarm-badge"
            >
              {alarmCount}
            </span>
          )}
        </a>
        <div
          className="w-9 h-9 rounded-full bg-[#0b1d4a] text-white text-xs font-bold flex items-center justify-center"
          title="Signed in as web operator (no login yet)"
        >
          OP
        </div>
      </div>
    </header>
  )
}
