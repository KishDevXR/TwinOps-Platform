import React, { useState } from 'react'
import type { LiveAssetTwin, AlarmItem } from '../types/twin'
import {
  X,
  Activity,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Sparkles,
} from 'lucide-react'

interface AssetSidePanelProps {
  asset: LiveAssetTwin | null
  alarms: AlarmItem[]
  onClose: () => void
  onOpenSimulation: (asset: LiveAssetTwin) => void
  onAcknowledgeAlarm: (id: string | number) => void
}

export const AssetSidePanel: React.FC<AssetSidePanelProps> = ({
  asset,
  alarms,
  onClose,
  onOpenSimulation,
  onAcknowledgeAlarm,
}) => {
  const [activeTab, setActiveTab] = useState<'metrics' | 'kpis' | 'alarms'>('metrics')

  if (!asset) return null

  const assetAlarms = alarms.filter((a) => a.asset_id === asset.asset_id)

  const getQualityBadge = (q: number) => {
    switch (q) {
      case 0:
        return <span className="text-[10px] text-emerald-400 font-semibold px-1 rounded bg-emerald-950 border border-emerald-800">Good</span>
      case 1:
        return <span className="text-[10px] text-amber-400 font-semibold px-1 rounded bg-amber-950 border border-amber-800">Uncertain</span>
      case 2:
        return <span className="text-[10px] text-rose-400 font-semibold px-1 rounded bg-rose-950 border border-rose-800">Bad</span>
      case 3:
        return <span className="text-[10px] text-slate-400 font-semibold px-1 rounded bg-slate-800 border border-slate-700">Stale</span>
      default:
        return null
    }
  }

  return (
    <aside
      className="absolute top-0 right-0 h-full w-96 bg-slate-900/95 border-l border-slate-800 shadow-2xl backdrop-blur-md z-30 flex flex-col text-slate-200 select-none animate-in slide-in-from-right duration-200"
      data-testid="asset-side-panel"
    >
      {/* Panel Header */}
      <div className="p-4 border-b border-slate-800 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono font-bold text-sky-400 text-base" data-testid="panel-asset-id">
              {asset.asset_id}
            </span>
            <span
              className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase ${
                asset.status_color === 'green'
                  ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                  : asset.status_color === 'red'
                  ? 'bg-rose-950 text-rose-400 border border-rose-800 animate-pulse'
                  : asset.status_color === 'amber'
                  ? 'bg-amber-950 text-amber-400 border border-amber-800'
                  : 'bg-slate-800 text-slate-400'
              }`}
              data-testid="panel-asset-status"
            >
              {asset.status}
            </span>
            <span className="text-[11px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
              Crit: {asset.criticality}
            </span>
          </div>
          <h2 className="text-sm font-semibold text-white leading-tight" data-testid="panel-asset-name">
            {asset.name}
          </h2>
          <div className="text-xs text-slate-400 mt-0.5">
            Line: {asset.line_id} • Type: {asset.type_id.replace('_', ' ')}
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
          aria-label="Close panel"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-800 text-xs font-medium">
        <button
          onClick={() => setActiveTab('metrics')}
          className={`flex-1 py-2.5 text-center border-b-2 transition flex items-center justify-center gap-1.5 ${
            activeTab === 'metrics'
              ? 'border-sky-500 text-sky-400 bg-sky-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          Live Metrics
        </button>
        <button
          onClick={() => setActiveTab('kpis')}
          className={`flex-1 py-2.5 text-center border-b-2 transition flex items-center justify-center gap-1.5 ${
            activeTab === 'kpis'
              ? 'border-sky-500 text-sky-400 bg-sky-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <TrendingUp className="w-3.5 h-3.5" />
          Derived KPIs
        </button>
        <button
          onClick={() => setActiveTab('alarms')}
          className={`flex-1 py-2.5 text-center border-b-2 transition flex items-center justify-center gap-1.5 relative ${
            activeTab === 'alarms'
              ? 'border-sky-500 text-sky-400 bg-sky-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
          Alarms
          {assetAlarms.length > 0 && (
            <span className="w-4 h-4 rounded-full bg-rose-500 text-white text-[10px] flex items-center justify-center font-bold">
              {assetAlarms.length}
            </span>
          )}
        </button>
      </div>

      {/* Tab Content Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {activeTab === 'metrics' && (
          <div className="space-y-3" data-testid="panel-metrics-tab">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Telemetry Metric</span>
              <span>Value / Quality</span>
            </div>
            <div className="space-y-2">
              {Object.entries(asset.metrics).map(([metricName, metric]) => (
                <div
                  key={metricName}
                  className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-800 flex items-center justify-between hover:border-slate-700 transition"
                  data-testid={`metric-row-${metricName}`}
                >
                  <div>
                    <div className="text-xs font-semibold text-slate-200">
                      {metricName.replace(/_/g, ' ')}
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                      source: scan 1000ms
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-sm font-bold text-sky-400">
                      {typeof metric.v === 'number' ? metric.v.toFixed(2) : metric.v}{' '}
                      <span className="text-xs font-normal text-slate-300">{metric.unit || ''}</span>
                    </div>
                    <div className="mt-0.5">{getQualityBadge(metric.q)}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Simulated Live Sparkline Indicator */}
            <div className="p-3 rounded-lg bg-slate-800/40 border border-slate-800 mt-4">
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="text-slate-400 font-medium">Telemetry Trend (10m)</span>
                <span className="text-emerald-400 text-[11px] flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Real-time Ingestion
                </span>
              </div>
              <div className="h-12 w-full flex items-end gap-1 pt-2">
                {[40, 45, 42, 50, 48, 55, 60, 58, 62, 59, 64, 61, 65, 63, 67].map((val, idx) => (
                  <div
                    key={idx}
                    className="flex-1 rounded-t bg-sky-500/60 hover:bg-sky-400 transition"
                    style={{ height: `${(val / 70) * 100}%` }}
                    title={`Point ${idx}: ${val}`}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'kpis' && (
          <div className="space-y-3" data-testid="panel-kpis-tab">
            <div className="text-xs text-slate-400 mb-2">
              Formula Evaluated KPIs (ISO 10816 / OEE Standard)
            </div>
            {Object.entries(asset.derived || {}).map(([kpiName, value]) => (
              <div
                key={kpiName}
                className="p-3 rounded-lg bg-slate-800/60 border border-slate-800 flex items-center justify-between"
                data-testid={`kpi-row-${kpiName}`}
              >
                <div>
                  <div className="text-xs font-semibold text-slate-200 capitalize">
                    {kpiName.replace(/_/g, ' ')}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5">Calculated in Twin service</div>
                </div>
                <div className="font-mono text-base font-bold text-emerald-400">
                  {typeof value === 'number' ? value.toFixed(1) : value}
                  {kpiName.includes('pct') ? '%' : ''}
                </div>
              </div>
            ))}

            {/* Anomaly Health Index */}
            <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-800">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-semibold text-slate-200">Anomaly Risk Score</span>
                <span className="font-mono font-bold text-sky-400">
                  {((asset.anomaly_score ?? 0.05) * 100).toFixed(0)} / 100
                </span>
              </div>
              <div className="w-full bg-slate-700 h-2 rounded-full overflow-hidden mt-2">
                <div
                  className={`h-full rounded-full ${
                    (asset.anomaly_score ?? 0.05) > 0.8
                      ? 'bg-rose-500'
                      : (asset.anomaly_score ?? 0.05) > 0.4
                      ? 'bg-amber-500'
                      : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min(100, (asset.anomaly_score ?? 0.05) * 100)}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'alarms' && (
          <div className="space-y-3" data-testid="panel-alarms-tab">
            {assetAlarms.length === 0 ? (
              <div className="text-center py-8 text-xs text-slate-400">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2 opacity-80" />
                No alarms registered for {asset.asset_id}
              </div>
            ) : (
              assetAlarms.map((a) => (
                <div
                  key={a.id}
                  className="p-3 rounded-lg bg-slate-800/80 border border-slate-700 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                        a.severity === 'critical' ? 'bg-rose-500 text-white' : 'bg-amber-500 text-slate-900'
                      }`}
                    >
                      {a.severity}
                    </span>
                    <span className="text-[10px] text-slate-400 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(a.raised_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="text-xs text-slate-200 font-medium">{a.message}</div>
                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[11px] text-slate-400">State: {a.state}</span>
                    {a.state === 'active' && (
                      <button
                        onClick={() => onAcknowledgeAlarm(a.id)}
                        className="px-2 py-1 text-xs rounded bg-sky-600 hover:bg-sky-500 text-white font-medium"
                      >
                        Acknowledge
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Footer Actions */}
      <div className="p-4 border-t border-slate-800 bg-slate-900/90 space-y-2">
        <button
          onClick={() => onOpenSimulation(asset)}
          className="w-full py-2.5 px-3 rounded-lg bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 text-white font-semibold text-xs flex items-center justify-center gap-2 shadow-lg transition"
          data-testid="btn-what-if-simulation"
        >
          <Sparkles className="w-4 h-4 text-sky-200" />
          Run What-If Simulation Sandbox
        </button>
      </div>
    </aside>
  )
}
