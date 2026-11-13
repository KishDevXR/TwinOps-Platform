import React, { useMemo } from 'react'
import { Activity, AlertTriangle, ArrowRight, Boxes, ClipboardList } from 'lucide-react'
import { AreaChart, type Point } from '../components/AreaChart'
import { MiniPlant3D } from '../components/PlantViewer3D/AssetModels'
import { Card, Empty, PageHeader, Pill, StatCard } from '../components/ui'
import { routeHref } from '../hooks/useHashRoute'
import { usePoll } from '../hooks/usePoll'
import type { AlarmItem, LiveAssetTwin } from '../types/twin'
import { InsightRow } from './InsightsPage'
import { pmNextDue, type Insight, type Part, type PmPlan, type WorkOrder } from './insights'

interface Bucket {
  bucket: string
  avg: number
}

const fmtDate = (d: Date | string | null) =>
  d ? new Date(d).toLocaleDateString(undefined, { day: '2-digit', month: 'short' }) : '—'

export const DashboardPage: React.FC<{
  twins: Record<string, LiveAssetTwin>
  alarms: AlarmItem[]
  insights: Insight[]
  workOrders: WorkOrder[] | null
  pmPlans: PmPlan[] | null
  parts: Part[] | null
}> = ({ twins, alarms, insights, workOrders, pmPlans, parts }) => {
  const metrics = usePoll<{ mttr_hours: number | null; open_work_orders: number }>('/api/v1/maintenance/metrics', 15000).data
  // last 60 one-minute averages of the main incomer; `from` is fixed per load so the URL is stable
  const from = useMemo(() => new Date(Date.now() - 60 * 60_000).toISOString(), [])
  const power = usePoll<Bucket[]>(
    `/api/v1/assets/EM-01/telemetry?metric=power_kw&agg=1m&from=${encodeURIComponent(from)}`,
    30000,
  ).data
  const points: Point[] = useMemo(() => (power ?? []).map((b) => ({ t: new Date(b.bucket), v: b.avg })), [power])
  const latest = points.length ? points[points.length - 1].v : null

  const all = Object.values(twins)
  const running = all.filter((t) => t.status_color === 'green').length
  const faults = all.filter((t) => t.status_color === 'red').length
  const critical = alarms.filter((a) => a.severity === 'critical').length
  const now = Date.now()
  const pmRows = (pmPlans ?? [])
    .map((p) => ({ p, due: pmNextDue(p) }))
    .sort((x, y) => (x.due?.getTime() ?? Infinity) - (y.due?.getTime() ?? Infinity))
  const lowParts = (parts ?? []).filter((p) => p.qty <= p.reorder_level)

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        <div className="xl:col-span-7 flex flex-col gap-5">
          <PageHeader title="Dashboard Overview" sub="Live condition, maintenance and stock across the Pune machining plant." />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              icon={<Boxes className="w-5 h-5" />}
              value={all.length}
              label="Total assets"
              sub={<span className="text-slate-500">2 lines + logistics</span>}
              onClick={() => (window.location.hash = routeHref({ page: 'assets', q: '' }))}
            />
            <StatCard
              icon={<Activity className="w-5 h-5" />}
              tone="green"
              value={all.length ? `${Math.round((running / all.length) * 100)}%` : '—'}
              label="Running now"
              sub={
                <span className={faults ? 'text-rose-600' : 'text-emerald-600'}>
                  {running} running · {faults} in fault
                </span>
              }
            />
            <StatCard
              icon={<AlertTriangle className="w-5 h-5" />}
              tone={alarms.length ? 'red' : 'violet'}
              value={alarms.length}
              label="Active alarms"
              sub={<span className={critical ? 'text-rose-600' : 'text-slate-500'}>{critical} critical</span>}
            />
            <StatCard
              icon={<ClipboardList className="w-5 h-5" />}
              tone="amber"
              value={metrics?.open_work_orders ?? '—'}
              label="Open work orders"
              sub={
                <span className="text-slate-500">
                  MTTR {metrics?.mttr_hours != null ? `${metrics.mttr_hours.toFixed(1)} h` : '—'}
                </span>
              }
            />
          </div>
        </div>
        <a
          href={routeHref({ page: 'plant' })}
          className="xl:col-span-5 relative rounded-2xl overflow-hidden border border-slate-200 shadow-sm min-h-[240px] block"
          aria-label="Open the 3D plant"
        >
          <div className="absolute inset-0">
            <MiniPlant3D assets={twins} />
          </div>
          <span className="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-white/90 text-xs font-semibold text-slate-700 shadow-sm">
            PUNE-01 · live
          </span>
          <span className="absolute bottom-3 right-3 inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold shadow">
            Open 3D plant <ArrowRight className="w-3.5 h-3.5" />
          </span>
        </a>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        <Card
          className="xl:col-span-8"
          title="Plant power demand"
          right={
            latest !== null ? (
              <span>
                Now <span className="font-semibold text-slate-900 tabular-nums">{latest.toFixed(1)} kW</span>
              </span>
            ) : null
          }
        >
          <p className="px-5 -mt-1 text-xs text-slate-500">Main incomer (EM-01), 1-minute averages, last hour</p>
          <div className="px-3 pb-4 pt-2">
            <AreaChart points={points} unit="kW" label="Plant power demand, kW" />
          </div>
        </Card>
        <Card
          className="xl:col-span-4"
          title="AI Insights"
          right={
            <a href={routeHref({ page: 'insights' })} className="inline-flex items-center gap-1 text-blue-600 font-semibold">
              View all <ArrowRight className="w-3.5 h-3.5" />
            </a>
          }
        >
          {insights.length === 0 ? (
            <Empty text="Nothing needs attention right now." />
          ) : (
            <ul className="px-5 pb-3 divide-y divide-slate-100">
              {insights.slice(0, 4).map((i) => (
                <InsightRow key={i.id} insight={i} compact />
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card title="Work orders" right={workOrders ? `${workOrders.filter((w) => !['completed', 'closed'].includes(w.status)).length} open` : null}>
          {!workOrders ? (
            <Empty text="Maintenance service unavailable" />
          ) : workOrders.length === 0 ? (
            <Empty text="No work orders" />
          ) : (
            <ul className="px-5 pb-3 divide-y divide-slate-100">
              {workOrders.slice(0, 5).map((w) => (
                <li key={w.id} className="py-2.5 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-900 truncate">{w.title}</span>
                    <span className="ml-auto">
                      <Pill tone={['completed', 'closed'].includes(w.status) ? 'green' : 'blue'}>{w.status.replace('_', ' ')}</Pill>
                    </span>
                  </div>
                  <div className="text-xs text-slate-500">
                    WO-{w.id} ·{' '}
                    <a className="text-blue-600" href={routeHref({ page: 'asset', id: w.asset_id })}>
                      {w.asset_id}
                    </a>{' '}
                    · {w.type} · due {fmtDate(w.due_at)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Preventive maintenance" right={pmPlans ? `${pmPlans.length} plans` : null}>
          {!pmPlans ? (
            <Empty text="Maintenance service unavailable" />
          ) : (
            <ul className="px-5 pb-3 divide-y divide-slate-100">
              {pmRows.slice(0, 5).map(({ p, due }) => {
                const overdue = due !== null && due.getTime() < now
                return (
                  <li key={p.id} className="py-2.5 text-sm flex items-start gap-2">
                    <div className="min-w-0">
                      <div className="font-medium text-slate-900 truncate">{p.name}</div>
                      <div className="text-xs text-slate-500">
                        <a className="text-blue-600" href={routeHref({ page: 'asset', id: p.asset_id })}>
                          {p.asset_id}
                        </a>{' '}
                        · {p.trigger_type === 'calendar' ? `every ${p.interval_days} d` : `every ${p.interval_hours} run-h`}
                      </div>
                    </div>
                    <span className="ml-auto shrink-0">
                      {due ? <Pill tone={overdue ? 'red' : 'grey'}>{`${overdue ? 'Overdue' : 'Due'} ${fmtDate(due)}`}</Pill> : <Pill>Meter-based</Pill>}
                    </span>
                  </li>
                )
              })}
            </ul>
          )}
        </Card>

        <Card title="Spare parts" right={parts ? `${lowParts.length} at reorder level` : null}>
          {!parts ? (
            <Empty text="Maintenance service unavailable" />
          ) : (
            <ul className="px-5 pb-3 divide-y divide-slate-100">
              {parts.slice(0, 5).map((p) => {
                const low = p.qty <= p.reorder_level
                return (
                  <li key={p.code} className="py-2.5 text-sm flex items-center gap-2">
                    <div className="min-w-0">
                      <div className="font-medium text-slate-900 truncate">{p.name}</div>
                      <div className="text-xs text-slate-500">
                        {p.code} · {p.location}
                      </div>
                    </div>
                    <div className="ml-auto text-right">
                      <div className={`font-semibold tabular-nums ${low ? 'text-rose-600' : 'text-slate-900'}`}>{p.qty}</div>
                      <div className="text-[11px] text-slate-400">min {p.reorder_level}</div>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
