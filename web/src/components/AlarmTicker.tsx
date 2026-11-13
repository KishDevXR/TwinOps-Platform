import React from 'react'
import type { AlarmItem } from '../types/twin'
import { AlertOctagon, CheckCircle2 } from 'lucide-react'

interface AlarmTickerProps {
  alarms: AlarmItem[]
  onSelectAlarmAsset: (assetId: string) => void
  onAcknowledge: (id: string | number) => void
}

export const AlarmTicker: React.FC<AlarmTickerProps> = ({
  alarms,
  onSelectAlarmAsset,
  onAcknowledge,
}) => {
  const activeAlarms = alarms.filter((a) => a.state === 'active')

  if (activeAlarms.length === 0) {
    return (
      <div className="h-9 bg-slate-900/90 border-b border-slate-800 px-4 flex items-center justify-between text-xs text-slate-400 select-none">
        <div className="flex items-center gap-2 text-emerald-400 font-medium">
          <CheckCircle2 className="w-4 h-4" />
          <span>All 25 assets nominal — No active alarms across Pune plant</span>
        </div>
      </div>
    )
  }

  return (
    <div
      className="h-9 bg-rose-950/40 border-b border-rose-900/50 px-4 flex items-center justify-between text-xs text-rose-200 select-none overflow-hidden"
      data-testid="alarm-ticker"
    >
      <div className="flex items-center gap-3 overflow-x-auto no-scrollbar py-1">
        <span className="flex items-center gap-1.5 font-bold uppercase text-rose-400 tracking-wider text-[11px] shrink-0">
          <AlertOctagon className="w-4 h-4 animate-bounce text-rose-500" />
          Active Alerts ({activeAlarms.length}):
        </span>

        {activeAlarms.map((alarm) => (
          <div
            key={alarm.id}
            className="flex items-center gap-2 px-2.5 py-0.5 rounded bg-slate-900/80 border border-rose-800/60 shrink-0 cursor-pointer hover:bg-slate-800 transition"
            onClick={() => onSelectAlarmAsset(alarm.asset_id)}
          >
            <span
              className={`px-1 py-0.2 rounded text-[10px] font-bold uppercase ${
                alarm.severity === 'critical'
                  ? 'bg-rose-500 text-white'
                  : 'bg-amber-500 text-slate-950'
              }`}
            >
              {alarm.severity}
            </span>
            <span className="font-semibold text-sky-400">{alarm.asset_id}</span>
            <span className="text-slate-300 max-w-xs truncate">{alarm.message}</span>
            <button
              onClick={(e) => {
                e.stopPropagation()
                onAcknowledge(alarm.id)
              }}
              className="ml-2 px-1.5 py-0.5 text-[10px] rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700"
              title="Acknowledge alarm"
            >
              Ack
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
