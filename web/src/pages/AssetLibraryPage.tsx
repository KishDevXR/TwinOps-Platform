import React, { useMemo, useRef, useState } from 'react'
import { LayoutGrid, Rows3, Search } from 'lucide-react'
import { AssetThumb, ThumbnailCanvas } from '../components/PlantViewer3D/AssetModels'
import { Card, Empty, PageHeader, Pill, StatusPill, Tabs } from '../components/ui'
import { LINE_NAMES, TYPE_GROUPS, TYPE_LABEL, keyReadings, type AssetRecord } from '../constants/assetTypes'
import { routeHref } from '../hooks/useHashRoute'
import { usePoll } from '../hooks/usePoll'
import type { LiveAssetTwin, StatusColor } from '../types/twin'

const CRIT_TONE = { A: 'red', B: 'amber', C: 'grey' } as const

export function filterAssets(
  register: AssetRecord[],
  twins: Record<string, LiveAssetTwin>,
  f: { q: string; group: string; line: string; status: string },
): AssetRecord[] {
  const q = f.q.trim().toLowerCase()
  const types = TYPE_GROUPS.find((g) => g.id === f.group)?.types
  return register
    .filter((a) => !types || types.includes(a.type_id))
    .filter((a) => f.line === 'all' || a.line_id === f.line)
    .filter((a) => f.status === 'all' || (twins[a.id]?.status_color ?? 'grey') === f.status)
    .filter((a) => !q || [a.id, a.name, a.make, a.model, a.serial_no, TYPE_LABEL[a.type_id]].some((s) => s?.toLowerCase().includes(q)))
    .sort((x, y) => x.id.localeCompare(y.id, undefined, { numeric: true }))
}

export const AssetLibraryPage: React.FC<{ twins: Record<string, LiveAssetTwin>; initialQuery: string }> = ({
  twins,
  initialQuery,
}) => {
  const register = usePoll<AssetRecord[]>('/api/v1/assets', 60000).data
  const [q, setQ] = useState(initialQuery)
  const [group, setGroup] = useState('all')
  const [line, setLine] = useState('all')
  const [status, setStatus] = useState('all')
  const [view, setView] = useState<'grid' | 'table'>('grid')
  const pageRef = useRef<HTMLDivElement>(null)

  const rows = useMemo(() => filterAssets(register ?? [], twins, { q, group, line, status }), [register, twins, q, group, line, status])
  const countIn = (g: string) => filterAssets(register ?? [], twins, { q: '', group: g, line: 'all', status: 'all' }).length

  return (
    <div className="flex flex-col gap-5" ref={pageRef}>
      <PageHeader title="Asset Library" sub="Every asset in the plant register, with its live state." />
      <Card>
        <div className="px-5 pt-4 flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 rounded-xl bg-slate-100 px-3.5 py-2 text-sm flex-1 min-w-[220px]">
            <Search className="w-4 h-4 text-slate-400" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by ID, name, type, make or serial…"
              aria-label="Filter assets"
              className="bg-transparent outline-none w-full text-slate-900 placeholder:text-slate-400"
            />
          </label>
          <select value={line} onChange={(e) => setLine(e.target.value)} aria-label="Filter by line" className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm">
            <option value="all">All lines</option>
            {Object.entries(LINE_NAMES).map(([id, n]) => (
              <option key={id} value={id}>
                {n}
              </option>
            ))}
          </select>
          <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status" className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm">
            <option value="all">Any status</option>
            <option value="green">Running</option>
            <option value="amber">Warning / idle</option>
            <option value="red">Fault / alarm</option>
            <option value="grey">Offline</option>
          </select>
          <div className="flex rounded-xl border border-slate-200 p-0.5" role="group" aria-label="Layout">
            {(
              [
                ['grid', LayoutGrid, 'Grid'],
                ['table', Rows3, 'Table'],
              ] as const
            ).map(([id, Icon, label]) => (
              <button
                key={id}
                onClick={() => setView(id)}
                aria-pressed={view === id}
                aria-label={`${label} view`}
                className={`p-1.5 rounded-lg ${view === id ? 'bg-blue-600 text-white' : 'text-slate-500 hover:text-slate-900'}`}
              >
                <Icon className="w-4 h-4" />
              </button>
            ))}
          </div>
        </div>
        <div className="px-5 pt-4">
          <Tabs
            tabs={[
              { id: 'all', label: `All assets (${register?.length ?? 0})` },
              ...TYPE_GROUPS.map((g) => ({ id: g.id, label: `${g.label} (${countIn(g.id)})` })),
            ]}
            active={group}
            onChange={setGroup}
          />
        </div>

        {!register ? (
          <Empty text="Loading asset register… (asset service, port 8002)" />
        ) : rows.length === 0 ? (
          <Empty text="No assets match these filters." />
        ) : view === 'grid' ? (
          <div className="p-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-4">
            {rows.map((a) => {
              const t = twins[a.id]
              return (
                <a
                  key={a.id}
                  href={routeHref({ page: 'asset', id: a.id })}
                  className="group rounded-xl border border-slate-200 overflow-hidden hover:border-blue-400 hover:shadow-md transition bg-white"
                  data-testid={`asset-card-${a.id}`}
                >
                  {t ? <AssetThumb asset={t} className="h-40 w-full bg-[#e7ecf7]" /> : <div className="h-40 bg-[#e7ecf7]" />}
                  <div className="p-3.5">
                    <div className="flex items-start gap-2">
                      <div className="min-w-0">
                        <div className="font-semibold text-slate-900 truncate group-hover:text-blue-700">{a.name}</div>
                        <div className="text-xs text-slate-500">
                          <span className="font-mono">{a.id}</span> · {TYPE_LABEL[a.type_id] ?? a.type_id}
                        </div>
                      </div>
                    </div>
                    <div className="mt-2.5 flex items-center gap-2">
                      <StatusPill color={(t?.status_color ?? 'grey') as StatusColor} status={t?.status} />
                      <Pill tone={CRIT_TONE[a.criticality as 'A' | 'B' | 'C'] ?? 'grey'}>Crit. {a.criticality}</Pill>
                    </div>
                    <div className="mt-2 text-xs text-slate-500 tabular-nums">{keyReadings(t).join(' · ') || ' '}</div>
                  </div>
                </a>
              )
            })}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm mt-2">
              <thead className="text-xs text-slate-500">
                <tr className="text-left border-b border-slate-100">
                  <th className="px-5 py-2.5 font-medium">Asset</th>
                  <th className="px-3 py-2.5 font-medium">Line</th>
                  <th className="px-3 py-2.5 font-medium">Make / model</th>
                  <th className="px-3 py-2.5 font-medium">Criticality</th>
                  <th className="px-3 py-2.5 font-medium">Status</th>
                  <th className="px-5 py-2.5 font-medium">Key readings</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((a) => {
                  const t = twins[a.id]
                  return (
                    <tr
                      key={a.id}
                      className="hover:bg-slate-50 cursor-pointer"
                      onClick={() => (window.location.hash = routeHref({ page: 'asset', id: a.id }))}
                      data-testid={`asset-row-${a.id}`}
                    >
                      <td className="px-5 py-2.5">
                        <div className="font-medium text-slate-900">{a.name}</div>
                        <div className="text-xs text-slate-500 font-mono">{a.id}</div>
                      </td>
                      <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{LINE_NAMES[a.line_id] ?? a.line_id}</td>
                      <td className="px-3 py-2.5">
                        <div className="text-slate-700">{a.make}</div>
                        <div className="text-xs text-slate-500">
                          {a.model} · {a.serial_no}
                        </div>
                      </td>
                      <td className="px-3 py-2.5">
                        <Pill tone={CRIT_TONE[a.criticality as 'A' | 'B' | 'C'] ?? 'grey'}>{a.criticality}</Pill>
                      </td>
                      <td className="px-3 py-2.5">
                        <StatusPill color={(t?.status_color ?? 'grey') as StatusColor} status={t?.status} />
                      </td>
                      <td className="px-5 py-2.5 text-xs text-slate-600 tabular-nums whitespace-nowrap">
                        {keyReadings(t).map((r) => (
                          <div key={r}>{r}</div>
                        ))}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {view === 'grid' && register && <ThumbnailCanvas eventSource={pageRef} />}
    </div>
  )
}
