import React, { useMemo, useRef, useState } from 'react'

export interface Point {
  t: Date
  v: number
}

const W = 640
const H = 220
const PAD = { l: 44, r: 12, t: 12, b: 26 }
const LINE = '#2563eb' // validated against the white surface (dataviz validate_palette)

/** Round-number ticks covering [lo, hi]. */
export function niceTicks(lo: number, hi: number, count = 4): number[] {
  if (!(hi > lo)) return [lo]
  const raw = (hi - lo) / count
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw
  const start = Math.floor(lo / step) * step
  const out: number[] = [Number(start.toFixed(6))]
  while (out[out.length - 1] < hi) out.push(Number((out[out.length - 1] + step).toFixed(6)))
  return out
}

const fmtTime = (d: Date) => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

/** Single-series area chart with a crosshair tooltip. The card title names the series. */
export const AreaChart: React.FC<{ points: Point[]; unit: string; label: string }> = ({ points, unit, label }) => {
  const svgRef = useRef<SVGSVGElement>(null)
  const [hover, setHover] = useState<number | null>(null)

  const geo = useMemo(() => {
    if (points.length < 2) return null
    const vs = points.map((p) => p.v)
    const ticks = niceTicks(Math.min(...vs), Math.max(...vs))
    const lo = ticks[0]
    const hi = ticks[ticks.length - 1] > lo ? ticks[ticks.length - 1] : lo + 1
    const t0 = points[0].t.getTime()
    const t1 = points[points.length - 1].t.getTime()
    const x = (t: Date) => PAD.l + ((t.getTime() - t0) / Math.max(1, t1 - t0)) * (W - PAD.l - PAD.r)
    const y = (v: number) => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b)
    const line = points.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join('')
    const area = `${line}L${x(points[points.length - 1].t).toFixed(1)},${H - PAD.b}L${PAD.l},${H - PAD.b}Z`
    const xTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => points[Math.round(f * (points.length - 1))])
    return { x, y, line, area, ticks, xTicks }
  }, [points])

  if (!geo) {
    return <div className="h-[220px] flex items-center justify-center text-sm text-slate-400">Collecting data…</div>
  }

  const onMove = (e: React.PointerEvent) => {
    const r = svgRef.current!.getBoundingClientRect()
    const px = ((e.clientX - r.left) / r.width) * W
    let best = 0
    for (let i = 1; i < points.length; i++) {
      if (Math.abs(geo.x(points[i].t) - px) < Math.abs(geo.x(points[best].t) - px)) best = i
    }
    setHover(best)
  }

  const hp = hover !== null ? points[hover] : null
  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto touch-none"
        role="img"
        aria-label={`${label}, ${points.length} points`}
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id="area-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={LINE} stopOpacity="0.22" />
            <stop offset="100%" stopColor={LINE} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {geo.ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.l} x2={W - PAD.r} y1={geo.y(t)} y2={geo.y(t)} stroke="#e2e8f0" strokeWidth="1" />
            <text x={PAD.l - 8} y={geo.y(t)} textAnchor="end" dominantBaseline="middle" fontSize="11" fill="#64748b">
              {t.toLocaleString()}
            </text>
          </g>
        ))}
        {geo.xTicks.map((p, i) => (
          <text
            key={i}
            x={geo.x(p.t)}
            y={H - 6}
            textAnchor={i === 0 ? 'start' : i === geo.xTicks.length - 1 ? 'end' : 'middle'}
            fontSize="11"
            fill="#64748b"
          >
            {fmtTime(p.t)}
          </text>
        ))}
        <path d={geo.area} fill="url(#area-fill)" />
        <path d={geo.line} fill="none" stroke={LINE} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {hp && (
          <g>
            <line x1={geo.x(hp.t)} x2={geo.x(hp.t)} y1={PAD.t} y2={H - PAD.b} stroke="#94a3b8" strokeWidth="1" />
            <circle cx={geo.x(hp.t)} cy={geo.y(hp.v)} r="5" fill={LINE} stroke="#fff" strokeWidth="2" />
          </g>
        )}
      </svg>
      {hp && (
        <div
          className="pointer-events-none absolute top-1 px-3 py-2 rounded-lg bg-white shadow-lg ring-1 ring-slate-200 text-xs"
          style={{
            left: `${(geo.x(hp.t) / W) * 100}%`,
            transform: geo.x(hp.t) > W * 0.6 ? 'translateX(calc(-100% - 10px))' : 'translateX(10px)',
          }}
        >
          <div className="text-slate-500">{fmtTime(hp.t)}</div>
          <div className="font-semibold text-slate-900 tabular-nums">
            {hp.v.toFixed(1)} {unit}
          </div>
        </div>
      )}
      <table className="sr-only">
        <caption>{label}</caption>
        <thead>
          <tr>
            <th>Time</th>
            <th>{unit}</th>
          </tr>
        </thead>
        <tbody>
          {points.map((p) => (
            <tr key={p.t.getTime()}>
              <td>{fmtTime(p.t)}</td>
              <td>{p.v.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
