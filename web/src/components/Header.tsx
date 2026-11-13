import React from 'react'
import { Activity, Bell, Wifi, WifiOff, RefreshCw, Cpu } from 'lucide-react'

interface HeaderProps {
  siteId: string
  connectionState: 'connected' | 'connecting' | 'disconnected'
  lastLatencyMs: number
  alarmCount: number
  onRefresh: () => void
  onOpenAlarms: () => void
}

export const Header: React.FC<HeaderProps> = ({
  siteId,
  connectionState,
  lastLatencyMs,
  alarmCount,
  onRefresh,
  onOpenAlarms,
}) => {
  return (
    <header className="h-14 bg-slate-900 border-b border-slate-800 px-4 flex items-center justify-between text-white select-none z-20">
      {/* Brand & Site */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400 font-bold">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <span className="font-bold tracking-tight text-lg bg-gradient-to-r from-sky-400 to-indigo-400 bg-clip-text text-transparent">
              TwinOps
            </span>
            <span className="text-xs text-slate-400 font-mono ml-2 border-l border-slate-700 pl-2">
              DIGITAL TWIN SUITE
            </span>
          </div>
        </div>

        {/* Site Pill */}
        <div className="flex items-center gap-1.5 ml-4 px-2.5 py-1 rounded bg-slate-800/80 border border-slate-700 text-xs">
          <span className="text-slate-400">Site:</span>
          <span className="font-semibold text-sky-400">{siteId}</span>
          <span className="text-[10px] text-slate-500 ml-1">(Pune Machining Pilot)</span>
        </div>
      </div>

      {/* Middle Status Indicators */}
      <div className="flex items-center gap-4 text-xs">
        {/* Latency & Connectivity */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800/70 border border-slate-700/80">
          {connectionState === 'connected' ? (
            <>
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <Wifi className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-slate-300">Live WS</span>
              <span className="font-mono text-emerald-400">{lastLatencyMs}ms</span>
            </>
          ) : connectionState === 'connecting' ? (
            <>
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
              <Activity className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-amber-300">Connecting...</span>
            </>
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-rose-500" />
              <WifiOff className="w-3.5 h-3.5 text-rose-400" />
              <span className="text-rose-400">Disconnected</span>
            </>
          )}
        </div>
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={onRefresh}
          className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
          title="Refresh twin snapshot"
          aria-label="Refresh twin snapshot"
        >
          <RefreshCw className="w-4 h-4" />
        </button>

        {/* Alarm button with badge */}
        <button
          onClick={onOpenAlarms}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition relative"
          aria-label="View alarms"
        >
          <Bell className="w-4 h-4 text-amber-400" />
          <span className="text-xs font-medium">Alarms</span>
          {alarmCount > 0 && (
            <span
              className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-rose-500 text-white animate-pulse"
              data-testid="alarm-badge"
            >
              {alarmCount}
            </span>
          )}
        </button>
      </div>
    </header>
  )
}
