import React, { useState } from 'react'
import { ArrowLeft, Box, FlaskConical } from 'lucide-react'
import { AssetPreview3D } from '../components/PlantViewer3D/AssetModels'
import { WhatIfSimulationModal } from '../components/WhatIfSimulationModal'
import { Card, Empty, Pill, StatusPill, Tabs } from '../components/ui'
import { LINE_NAMES, TYPE_LABEL, fmtValue, type AssetRecord } from '../constants/assetTypes'
import { routeHref } from '../hooks/useHashRoute'
import { usePoll } from '../hooks/usePoll'
import type { AlarmItem, LiveAssetTwin } from '../types/twin'
import { pmNextDue, type PmPlan, type WorkOrder } from './insights'

const QUALITY = ['Good', 'Uncertain', 'Bad', 'Stale']
const fmtDate = (d: Date | string | null) => (d ? new Date(d).toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' }) : '—')

export const AssetDetailPage: React.FC<{
  id: string
  twin: LiveAssetTwin | undefined
  alarms: AlarmItem[]
  onAcknowledge: (id: string | number) => void
  pmPlans: PmPlan[] | null
}> = ({ id, twin, alarms, onAcknowledge, pmPlans }) => {
  const record = usePoll<AssetRecord>(`/api/v1/assets/${encodeURIComponent(id)}`, 60000).data
  const workOrders = usePoll<{ work_orders: WorkOrder[] }>(`/api/v1/work-orders?asset_id=${encodeURIComponent(id)}`, 15000).data?.work_orders
  const [tab, setTab] = useState<'live' | 'alarms' | 'work' | 'pm'>('live')
  const [simOpen, setSimOpen] = useState(false)

  if (!twin && !record) {
    return (
      <Card>
        <Empty text={`Loading ${id}…`} />
      </Card>
    )
  }
  const assetAlarms = alarms.filter((a) => a.asset_id === id)
  const plans = (pmPlans ?? []).filter((p) => p.asset_id === id)
  const name = record?.name ?? twin?.name ?? id
  const typeId = record?.type_id ?? twin?.type_id ?? ''

  const details: [string, React.ReactNode][] = [
    ['Asset ID', <span className="font-mono">{id}</span>],
    ['Line', LINE_NAMES[record?.line_id ?? twin?.line_id ?? ''] ?? record?.line_id ?? '—'],
    ['Make', record?.make ?? '—'],
    ['Model', record?.model ?? '—'],
    ['Serial no.', record?.serial_no ?? '—'],
    ['Lifecycle', record?.lifecycle_state ?? '—'],
    ['Installed', fmtDate(record?.install_date ?? null)],
    ['Last update', twin?.last_seen ? new Date(twin.last_seen).toLocaleTimeString() : '—'],
  ]

  return (
    <div className="flex flex-col gap-5">
      <a href={routeHref({ page: 'assets', q: '' })} className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 w-fit">
        <ArrowLeft className="w-4 h-4" /> Asset Library
      </a>
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 items-start">
        <Card className="xl:col-span-8 overflow-hidden">
          <div className="h-[420px] relative" data-testid="asset-preview">
            {twin ? <AssetPreview3D asset={twin} /> : <div className="h-full bg-[#dfe6f5]" />}
            <span className="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-white/90 text-xs font-medium text-slate-600 shadow-sm">
              Drag to rotate · scroll to zoom
            </span>
          </div>
          <div className="px-5 pt-3">
            <Tabs
              tabs={[
                { id: 'live' as const, label: 'Live metrics' },
                { id: 'alarms' as const, label: `Alarms (${assetAlarms.length})` },
                { id: 'work' as const, label: `Work orders (${workOrders?.length ?? 0})` },
                { id: 'pm' as const, label: `Maintenance plans (${plans.length})` },
              ]}
              active={tab}
              onChange={setTab}
            />
          </div>
          {tab === 'live' &&
            (twin && Object.keys(twin.metrics).length ? (
              <div className="p-5 grid grid-cols-2 md:grid-cols-3 gap-3">
                {Object.entries(twin.metrics).map(([k, m]) => (
                  <div key={k} className="rounded-xl bg-slate-50 border border-slate-100 px-3.5 py-2.5" data-testid={`metric-${k}`}>
                    <div className="text-xs text-slate-500 truncate">{k.replace(/_/g, ' ')}</div>
                    <div className="text-lg font-semibold text-slate-900 tabular-nums">
                      {typeof m.v === 'number' ? fmtValue(m.v) : String(m.v)}
                      <span className="text-xs font-normal text-slate-500 ml-1">{m.unit ?? ''}</span>
                    </div>
                    {m.q !== 0 && <Pill tone={m.q === 2 ? 'red' : 'amber'}>{QUALITY[m.q] ?? 'Unknown'}</Pill>}
                  </div>
                ))}
              </div>
            ) : (
              <Empty text="No live telemetry yet." />
            ))}
          {tab === 'alarms' &&
            (assetAlarms.length === 0 ? (
              <Empty text="No active alarms on this asset." />
            ) : (
              <ul className="divide-y divide-slate-100">
                {assetAlarms.map((a) => (
                  <li key={a.id} className="px-5 py-3 flex items-center gap-3 text-sm">
                    <Pill tone={a.severity === 'critical' || a.severity === 'high' ? 'red' : 'amber'}>{a.severity}</Pill>
                    <span className="text-slate-800">{a.message}</span>
                    <button onClick={() => onAcknowledge(a.id)} className="ml-auto px-3 py-1 rounded-lg border border-slate-200 text-xs font-semibold hover:bg-slate-50">
                      Acknowledge
                    </button>
                  </li>
                ))}
              </ul>
            ))}
          {tab === 'work' &&
            (!workOrders?.length ? (
              <Empty text="No work orders for this asset." />
            ) : (
              <ul className="divide-y divide-slate-100">
                {workOrders.map((w) => (
                  <li key={w.id} className="px-5 py-3 text-sm flex items-center gap-3">
                    <div>
                      <div className="font-medium text-slate-900">{w.title}</div>
                      <div className="text-xs text-slate-500">
                        WO-{w.id} · {w.type} · {w.priority} priority · due {fmtDate(w.due_at)}
                      </div>
                    </div>
                    <span className="ml-auto">
                      <Pill tone={['completed', 'closed'].includes(w.status) ? 'green' : 'blue'}>{w.status.replace('_', ' ')}</Pill>
                    </span>
                  </li>
                ))}
              </ul>
            ))}
          {tab === 'pm' &&
            (plans.length === 0 ? (
              <Empty text="No preventive maintenance plans for this asset." />
            ) : (
              <ul className="divide-y divide-slate-100">
                {plans.map((p) => {
                  const due = pmNextDue(p)
                  const overdue = due !== null && due.getTime() < Date.now()
                  return (
                    <li key={p.id} className="px-5 py-3 text-sm flex items-center gap-3">
                      <div>
                        <div className="font-medium text-slate-900">{p.name}</div>
                        <div className="text-xs text-slate-500">
                          {p.trigger_type === 'calendar' ? `Every ${p.interval_days} days` : `Every ${p.interval_hours} run-hours`} · last done{' '}
                          {fmtDate(p.last_done)}
                        </div>
                      </div>
                      <span className="ml-auto">
                        {due ? <Pill tone={overdue ? 'red' : 'grey'}>{`${overdue ? 'Overdue' : 'Due'} ${fmtDate(due)}`}</Pill> : <Pill>Meter-based</Pill>}
                      </span>
                    </li>
                  )
                })}
              </ul>
            ))}
        </Card>

        <div className="xl:col-span-4 flex flex-col gap-5">
          <Card>
            <div className="p-5">
              <h1 className="text-xl font-bold text-slate-900">{name}</h1>
              <div className="mt-2 flex flex-wrap gap-2">
                <StatusPill color={twin?.status_color ?? 'grey'} status={twin?.status} />
                <Pill tone="blue">{TYPE_LABEL[typeId] ?? typeId}</Pill>
                {record && <Pill tone={record.criticality === 'A' ? 'red' : record.criticality === 'B' ? 'amber' : 'grey'}>Criticality {record.criticality}</Pill>}
              </div>
              {twin?.status_reasons?.length ? (
                <p className="mt-3 text-sm text-amber-700 bg-amber-50 rounded-lg px-3 py-2">{twin.status_reasons.join('; ')}</p>
              ) : null}
              <dl className="mt-4 divide-y divide-slate-100 text-sm">
                {details.map(([k, v]) => (
                  <div key={k} className="flex py-2">
                    <dt className="w-28 text-slate-500">{k}</dt>
                    <dd className="text-slate-900">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </Card>
          <Card title="Actions">
            <div className="px-5 pb-5 flex flex-col gap-2">
              <a
                href={routeHref({ page: 'plant', id })}
                className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 text-white text-sm font-semibold py-2.5 hover:bg-blue-700"
              >
                <Box className="w-4 h-4" /> Show in 3D plant
              </a>
              {twin && (
                <button
                  onClick={() => setSimOpen(true)}
                  className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 text-sm font-semibold py-2.5 text-slate-700 hover:bg-slate-50"
                >
                  <FlaskConical className="w-4 h-4" /> What-if simulation
                </button>
              )}
            </div>
          </Card>
        </div>
      </div>
      {simOpen && twin && <WhatIfSimulationModal asset={twin} onClose={() => setSimOpen(false)} />}
    </div>
  )
}
