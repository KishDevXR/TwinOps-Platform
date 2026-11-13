import React from 'react'
import type { StatusColor } from '../types/twin'

/** White rounded panel, the basic surface of every page. */
export const Card: React.FC<{
  title?: React.ReactNode
  right?: React.ReactNode
  className?: string
  children: React.ReactNode
}> = ({ title, right, className = '', children }) => (
  <section className={`rounded-2xl bg-white border border-slate-200/80 shadow-sm ${className}`}>
    {(title || right) && (
      <header className="flex items-center gap-3 px-5 pt-4 pb-2">
        {title && <h2 className="text-[15px] font-semibold text-slate-900">{title}</h2>}
        {right && <div className="ml-auto text-sm text-slate-500">{right}</div>}
      </header>
    )}
    {children}
  </section>
)

const TONES = {
  blue: 'bg-blue-50 text-blue-600',
  violet: 'bg-violet-50 text-violet-600',
  green: 'bg-emerald-50 text-emerald-600',
  amber: 'bg-amber-50 text-amber-600',
  red: 'bg-rose-50 text-rose-600',
  slate: 'bg-slate-100 text-slate-600',
} as const
export type Tone = keyof typeof TONES

/** Stat tile: icon chip, big number, label, one line of context. */
export const StatCard: React.FC<{
  icon: React.ReactNode
  tone?: Tone
  value: React.ReactNode
  label: string
  sub?: React.ReactNode
  onClick?: () => void
}> = ({ icon, tone = 'blue', value, label, sub, onClick }) => (
  <Card className={onClick ? 'cursor-pointer hover:border-blue-300 transition' : ''}>
    <div className="p-5" onClick={onClick}>
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${TONES[tone]}`}>{icon}</div>
      <div className="mt-3 text-[28px] leading-none font-bold text-slate-900 tabular-nums">{value}</div>
      <div className="mt-1.5 text-sm text-slate-500">{label}</div>
      {sub && <div className="mt-2 text-xs font-medium">{sub}</div>}
    </div>
  </Card>
)

export const IconChip: React.FC<{ tone?: Tone; children: React.ReactNode }> = ({ tone = 'blue', children }) => (
  <div className={`w-9 h-9 shrink-0 rounded-xl flex items-center justify-center ${TONES[tone]}`}>{children}</div>
)

const PILLS = {
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-700 ring-amber-200',
  red: 'bg-rose-50 text-rose-700 ring-rose-200',
  grey: 'bg-slate-100 text-slate-600 ring-slate-200',
  blue: 'bg-blue-50 text-blue-700 ring-blue-200',
} as const

export const Pill: React.FC<{ tone?: keyof typeof PILLS; children: React.ReactNode }> = ({ tone = 'grey', children }) => (
  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ring-1 ring-inset ${PILLS[tone]}`}>
    {children}
  </span>
)

const STATUS_LABEL: Record<StatusColor, string> = {
  green: 'Running',
  amber: 'Warning / idle',
  red: 'Fault / alarm',
  grey: 'Offline',
}

/** Status pill: dot + word, so state never relies on colour alone. */
export const StatusPill: React.FC<{ color: StatusColor; status?: string }> = ({ color, status }) => (
  <Pill tone={color}>
    <span
      className={`w-1.5 h-1.5 rounded-full ${
        { green: 'bg-emerald-500', amber: 'bg-amber-500', red: 'bg-rose-500', grey: 'bg-slate-400' }[color]
      }`}
    />
    {status ? status.charAt(0) + status.slice(1).toLowerCase() : STATUS_LABEL[color]}
  </Pill>
)

export const Empty: React.FC<{ text: string }> = ({ text }) => (
  <div className="px-5 py-8 text-center text-sm text-slate-400">{text}</div>
)

export const PageHeader: React.FC<{ title: string; sub?: string; right?: React.ReactNode }> = ({ title, sub, right }) => (
  <div className="flex items-end gap-4 flex-wrap">
    <div>
      <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{title}</h1>
      {sub && <p className="text-sm text-slate-500 mt-1">{sub}</p>}
    </div>
    {right && <div className="ml-auto">{right}</div>}
  </div>
)

/** Underlined tab strip, as in the reference. */
export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: T; label: React.ReactNode }[]
  active: T
  onChange: (id: T) => void
}) {
  return (
    <div className="flex gap-6 border-b border-slate-200 text-sm" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          onClick={() => onChange(t.id)}
          className={`pb-2.5 -mb-px border-b-2 font-medium transition ${
            active === t.id ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}
