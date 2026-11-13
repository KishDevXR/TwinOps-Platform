import React, { useState } from 'react'
import { AlertOctagon, AlertTriangle, ArrowRight, CheckCircle2, Info } from 'lucide-react'
import { Card, IconChip, PageHeader, Pill, Tabs } from '../components/ui'
import { routeHref } from '../hooks/useHashRoute'
import type { Category, Insight, Severity } from './insights'

const SEV: Record<Severity, { tone: 'red' | 'amber' | 'blue'; icon: React.ElementType; label: string }> = {
  critical: { tone: 'red', icon: AlertOctagon, label: 'Critical' },
  warning: { tone: 'amber', icon: AlertTriangle, label: 'Warning' },
  info: { tone: 'blue', icon: Info, label: 'Info' },
}

/** One insight: severity icon + label, title, detail, link to the asset. */
export const InsightRow: React.FC<{ insight: Insight; compact?: boolean }> = ({ insight, compact }) => {
  const s = SEV[insight.severity]
  const Icon = s.icon
  return (
    <li className={`flex gap-3 ${compact ? 'py-3' : 'p-4'}`} data-testid={`insight-${insight.id}`}>
      <IconChip tone={s.tone}>
        <Icon className="w-4 h-4" aria-hidden />
      </IconChip>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-slate-900 text-sm">{insight.title}</span>
          {!compact && <Pill tone={s.tone === 'blue' ? 'blue' : s.tone === 'red' ? 'red' : 'amber'}>{s.label}</Pill>}
          {!compact && <Pill>{insight.category}</Pill>}
        </div>
        <p className={`text-sm text-slate-500 ${compact ? 'line-clamp-2' : ''}`}>{insight.detail}</p>
        {insight.assetId && !compact && (
          <a
            href={routeHref({ page: 'asset', id: insight.assetId })}
            className="inline-flex items-center gap-1 mt-1 text-xs font-semibold text-blue-600 hover:underline"
          >
            Open {insight.assetId} <ArrowRight className="w-3 h-3" />
          </a>
        )}
      </div>
    </li>
  )
}

const CATEGORIES: Category[] = ['Live condition', 'Alarms', 'Maintenance', 'Inventory', 'Logistics']

export const InsightsPage: React.FC<{ insights: Insight[] }> = ({ insights }) => {
  const [cat, setCat] = useState<'all' | Category>('all')
  const shown = cat === 'all' ? insights : insights.filter((i) => i.category === cat)
  const count = (s: Severity) => insights.filter((i) => i.severity === s).length

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="AI Insights"
        sub="What needs attention across the plant, checked continuously against live data, alarms, maintenance and stock."
      />
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {(['critical', 'warning', 'info'] as Severity[]).map((s) => {
          const Icon = SEV[s].icon
          return (
            <Card key={s}>
              <div className="p-5 flex items-center gap-3">
                <IconChip tone={SEV[s].tone}>
                  <Icon className="w-4 h-4" aria-hidden />
                </IconChip>
                <div>
                  <div className="text-2xl font-bold text-slate-900 tabular-nums">{count(s)}</div>
                  <div className="text-sm text-slate-500">{SEV[s].label}</div>
                </div>
              </div>
            </Card>
          )
        })}
      </div>
      <Card>
        <div className="px-5 pt-4">
          <Tabs
            tabs={[
              { id: 'all' as const, label: `All (${insights.length})` },
              ...CATEGORIES.map((c) => ({ id: c, label: `${c} (${insights.filter((i) => i.category === c).length})` })),
            ]}
            active={cat}
            onChange={setCat}
          />
        </div>
        {shown.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-12 text-slate-500">
            <CheckCircle2 className="w-8 h-8 text-emerald-500" aria-hidden />
            <span className="text-sm">Nothing needs attention here right now.</span>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {shown.map((i) => (
              <InsightRow key={i.id} insight={i} />
            ))}
          </ul>
        )}
        <p className="px-5 py-3 border-t border-slate-100 text-xs text-slate-400">
          Insights are rule-based checks (limits from each asset type's twin template, PM due dates, reorder levels).
          Predictive anomaly and remaining-life models are not shown until they are trained on real history.
        </p>
      </Card>
    </div>
  )
}
