// Rule-based insights computed from live service data (no LLM). Each rule is one data check.
import type { AlarmItem, LiveAssetTwin } from '../types/twin'

export type Severity = 'critical' | 'warning' | 'info'
export type Category = 'Live condition' | 'Alarms' | 'Maintenance' | 'Inventory' | 'Logistics'

export interface Insight {
  id: string
  severity: Severity
  category: Category
  title: string
  detail: string
  assetId?: string
}

export interface PmPlan {
  id: string
  asset_id: string
  name: string
  trigger_type: string
  interval_days: number | null
  interval_hours: number | null
  last_done: string | null
}
export interface WorkOrder {
  id: number
  asset_id: string
  title: string
  type: string
  priority: string
  status: string
  due_at: string | null
}
export interface Part {
  code: string
  name: string
  qty: number
  reorder_level: number
  location: string
}

const DAY_MS = 86_400_000
const CLOSED = new Set(['completed', 'closed'])

/** Next calendar due date of a PM plan, or null for meter-based plans. */
export function pmNextDue(plan: PmPlan): Date | null {
  if (plan.trigger_type !== 'calendar' || !plan.interval_days || !plan.last_done) return null
  return new Date(new Date(plan.last_done).getTime() + plan.interval_days * DAY_MS)
}

const num = (t: LiveAssetTwin, m: string) => Number(t.metrics?.[m]?.v)

export function buildInsights(input: {
  twins: Record<string, LiveAssetTwin>
  alarms: AlarmItem[]
  pmPlans: PmPlan[] | null
  workOrders: WorkOrder[] | null
  parts: Part[] | null
  now?: number
}): Insight[] {
  const now = input.now ?? Date.now()
  const out: Insight[] = []

  for (const t of Object.values(input.twins)) {
    const reasons = t.status_reasons ?? []
    if (t.status_color === 'red') {
      out.push({
        id: `fault-${t.asset_id}`,
        severity: 'critical',
        category: 'Live condition',
        title: `${t.asset_id} is in ${t.status === 'FAULT' ? 'fault' : 'alarm'}`,
        detail: reasons.length ? reasons.join('; ') : `${t.name} reports status ${t.status}.`,
        assetId: t.asset_id,
      })
    } else if (t.status_color === 'amber' && reasons.length) {
      // amber with no reason just means idle, which is not a problem
      out.push({
        id: `warn-${t.asset_id}`,
        severity: 'warning',
        category: 'Live condition',
        title: `${t.asset_id} above a warning limit`,
        detail: reasons.join('; '),
        assetId: t.asset_id,
      })
    } else if (t.status_color === 'grey' && t.is_stale) {
      out.push({
        id: `stale-${t.asset_id}`,
        severity: 'warning',
        category: 'Live condition',
        title: `No data from ${t.asset_id}`,
        detail: reasons.length ? reasons.join('; ') : `${t.name} has stopped reporting telemetry.`,
        assetId: t.asset_id,
      })
    }
    if (t.type_id === 'forklift' && num(t, 'battery_pct') < 25) {
      out.push({
        id: `battery-${t.asset_id}`,
        severity: 'warning',
        category: 'Logistics',
        title: `${t.asset_id} battery low`,
        detail: `Battery at ${Math.round(num(t, 'battery_pct'))}%; it is heading to the charger.`,
        assetId: t.asset_id,
      })
    }
    if (t.type_id === 'loading_dock' && num(t, 'truck_dwell_s') > 900) {
      out.push({
        id: `dwell-${t.asset_id}`,
        severity: 'warning',
        category: 'Logistics',
        title: `Truck waiting long at ${t.asset_id}`,
        detail: `Docked for ${Math.round(num(t, 'truck_dwell_s') / 60)} min (limit 15 min).`,
        assetId: t.asset_id,
      })
    }
  }

  for (const a of input.alarms) {
    out.push({
      id: `alarm-${a.id}`,
      severity: a.severity === 'critical' || a.severity === 'high' ? 'critical' : a.severity === 'medium' ? 'warning' : 'info',
      category: 'Alarms',
      title: `${a.severity.toUpperCase()} alarm on ${a.asset_id}`,
      detail: a.message,
      assetId: a.asset_id,
    })
  }

  for (const p of input.pmPlans ?? []) {
    const due = pmNextDue(p)
    if (!due) continue
    const days = Math.floor((due.getTime() - now) / DAY_MS)
    if (due.getTime() < now) {
      out.push({
        id: `pm-${p.id}`,
        severity: 'warning',
        category: 'Maintenance',
        title: `PM overdue on ${p.asset_id}`,
        detail: `${p.name} was due ${due.toLocaleDateString()}.`,
        assetId: p.asset_id,
      })
    } else if (days <= 7) {
      out.push({
        id: `pm-${p.id}`,
        severity: 'info',
        category: 'Maintenance',
        title: `PM due soon on ${p.asset_id}`,
        detail: `${p.name} is due ${due.toLocaleDateString()}.`,
        assetId: p.asset_id,
      })
    }
  }

  for (const w of input.workOrders ?? []) {
    if (!CLOSED.has(w.status) && w.due_at && new Date(w.due_at).getTime() < now) {
      out.push({
        id: `wo-${w.id}`,
        severity: 'warning',
        category: 'Maintenance',
        title: `Work order WO-${w.id} overdue`,
        detail: `${w.title} (${w.asset_id}) was due ${new Date(w.due_at).toLocaleDateString()}.`,
        assetId: w.asset_id,
      })
    }
  }

  for (const p of input.parts ?? []) {
    if (p.qty <= p.reorder_level) {
      out.push({
        id: `part-${p.code}`,
        severity: 'warning',
        category: 'Inventory',
        title: `Reorder ${p.name}`,
        detail: `${p.qty} in stock at ${p.location}; reorder level is ${p.reorder_level}.`,
      })
    }
  }

  const rank: Record<Severity, number> = { critical: 0, warning: 1, info: 2 }
  return out.sort((a, b) => rank[a.severity] - rank[b.severity])
}
