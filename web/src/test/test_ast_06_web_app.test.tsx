import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { PILOT_ASSETS_INITIAL } from '../constants/pilotAssets'
import { keyReadings, type AssetRecord } from '../constants/assetTypes'
import { parseRoute, routeHref } from '../hooks/useHashRoute'
import { buildInsights, pmNextDue } from '../pages/insights'
import { filterAssets } from '../pages/AssetLibraryPage'
import { DashboardPage } from '../pages/DashboardPage'
import { AreaChart, niceTicks } from '../components/AreaChart'
import { UsersPage } from '../pages/UsersPage'
import type { LiveAssetTwin } from '../types/twin'

// 3D needs WebGL, which jsdom lacks
vi.mock('../components/PlantViewer3D/AssetModels', () => ({
  MiniPlant3D: () => <div data-testid="mini-plant" />,
  AssetPreview3D: () => <div />,
  AssetThumb: () => <div />,
  ThumbnailCanvas: () => null,
}))

const twin = (id: string, patch: Partial<LiveAssetTwin>): LiveAssetTwin => ({ ...PILOT_ASSETS_INITIAL[id], ...patch })
const rec = (id: string, type_id: string, line_id: string, make = 'Acme'): AssetRecord => ({
  id,
  name: `${id} name`,
  type_id,
  line_id,
  make,
  model: 'M1',
  serial_no: `S-${id}`,
  criticality: 'A',
  lifecycle_state: 'Operating',
  install_date: null,
})

afterEach(() => vi.unstubAllGlobals())

describe('AST-06: web app routing', () => {
  it('parses and builds hash routes', () => {
    expect(parseRoute('#/assets/CNC-01')).toEqual({ page: 'asset', id: 'CNC-01' })
    expect(parseRoute('#/assets?q=pump')).toEqual({ page: 'assets', q: 'pump' })
    expect(parseRoute('#/plant/FLT-01')).toEqual({ page: 'plant', id: 'FLT-01' })
    expect(parseRoute('#/nonsense')).toEqual({ page: 'dashboard' })
    expect(parseRoute('')).toEqual({ page: 'dashboard' })
    expect(routeHref({ page: 'asset', id: 'CNC-01' })).toBe('#/assets/CNC-01')
    expect(parseRoute(routeHref({ page: 'assets', q: 'a b' }))).toEqual({ page: 'assets', q: 'a b' })
  })
})

describe('AST-06: insights from live data', () => {
  const now = new Date('2026-11-13T12:00:00Z').getTime()

  it('flags faults, real warnings, low battery, overdue PM and low stock; ignores plain idle', () => {
    const out = buildInsights({
      twins: {
        'CNC-04': twin('CNC-04', { status: 'FAULT', status_color: 'red', status_reasons: [] }),
        'CNC-03': twin('CNC-03', { status_color: 'amber', status_reasons: ['tool_wear_min (215.0 min) >= Warning High 200.0'] }),
        'COMP-02': twin('COMP-02', { status: 'IDLE', status_color: 'amber', status_reasons: [] }),
        'FLT-02': twin('FLT-02', { metrics: { battery_pct: { v: 18, q: 0 } } }),
      },
      alarms: [],
      pmPlans: [
        { id: 'PM1', asset_id: 'CNC-01', name: 'Monthly PM', trigger_type: 'calendar', interval_days: 30, interval_hours: null, last_done: '2026-10-01T00:00:00Z' },
      ],
      workOrders: [],
      parts: [{ code: 'B1', name: 'Bearing', qty: 2, reorder_level: 5, location: 'A1' }],
      now,
    })
    const ids = out.map((i) => i.id)
    expect(ids[0]).toBe('fault-CNC-04') // critical sorts first
    expect(ids).toContain('warn-CNC-03')
    expect(ids).not.toContain('warn-COMP-02')
    expect(ids).toContain('battery-FLT-02')
    expect(ids).toContain('pm-PM1')
    expect(ids).toContain('part-B1')
  })

  it('computes calendar PM due dates', () => {
    const plan = { id: 'p', asset_id: 'X', name: 'PM', interval_hours: null }
    expect(pmNextDue({ ...plan, trigger_type: 'calendar', interval_days: 30, last_done: '2026-10-14T00:00:00Z' })?.toISOString()).toBe(
      '2026-11-13T00:00:00.000Z',
    )
    expect(pmNextDue({ ...plan, trigger_type: 'meter', interval_days: null, last_done: null })).toBeNull()
  })
})

describe('AST-06: asset library', () => {
  const register = [rec('CNC-01', 'cnc_machine', 'LINE-01', 'Kaveri'), rec('PUMP-01', 'centrifugal_pump', 'LINE-01'), rec('FLT-01', 'forklift', 'LOG-01')]
  const twins = { 'CNC-01': twin('CNC-01', { status_color: 'red' }), 'PUMP-01': twin('PUMP-01', { status_color: 'green' }) }
  const f = (o: Partial<{ q: string; group: string; line: string; status: string }>) =>
    filterAssets(register, twins, { q: '', group: 'all', line: 'all', status: 'all', ...o }).map((a) => a.id)

  it('filters by type group, line, status and free text', () => {
    expect(f({})).toEqual(['CNC-01', 'FLT-01', 'PUMP-01'])
    expect(f({ group: 'utilities' })).toEqual(['PUMP-01'])
    expect(f({ line: 'LOG-01' })).toEqual(['FLT-01'])
    expect(f({ status: 'red' })).toEqual(['CNC-01'])
    expect(f({ status: 'grey' })).toEqual(['FLT-01']) // no live twin counts as offline
    expect(f({ q: 'kaveri' })).toEqual(['CNC-01'])
    expect(f({ q: 'forklift' })).toEqual(['FLT-01']) // matches the type label
  })

  it('formats key readings with units', () => {
    const flt = twin('FLT-01', { metrics: { battery_pct: { v: 87.4, q: 0, unit: '%' }, load_kg: { v: 450, q: 0, unit: 'kg' } } })
    expect(keyReadings(flt)).toEqual(['Battery 87.4 %', 'Load 450 kg'])
    expect(keyReadings(undefined)).toEqual([])
  })
})

describe('AST-06: power trend chart', () => {
  it('uses round ticks covering the data', () => {
    const t = niceTicks(117.6, 125.9)
    expect(t[0]).toBeLessThanOrEqual(117.6)
    expect(t[t.length - 1]).toBeGreaterThanOrEqual(125.9)
  })

  it('draws the series and exposes it as a table', () => {
    const base = new Date('2026-11-13T10:00:00Z').getTime()
    const points = [120, 122.5, 121].map((v, i) => ({ t: new Date(base + i * 60000), v }))
    const { container } = render(<AreaChart points={points} unit="kW" label="Plant power" />)
    expect(container.querySelectorAll('svg > path').length).toBe(2) // area + line
    expect(screen.getByText('122.5')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Plant power, 3 points' })).toBeInTheDocument()
  })

  it('says so when there is not enough data', () => {
    render(<AreaChart points={[]} unit="kW" label="x" />)
    expect(screen.getByText('Collecting data…')).toBeInTheDocument()
  })
})

describe('AST-06: pages', () => {
  it('dashboard shows live counts, alarms and insights from the services', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => ({
        ok: true,
        json: async () => (url.startsWith('/api/v1/maintenance/metrics') ? { mttr_hours: 2, open_work_orders: 4 } : []),
      })),
    )
    render(
      <DashboardPage
        twins={{ ...PILOT_ASSETS_INITIAL, 'CNC-04': twin('CNC-04', { status: 'FAULT', status_color: 'red' }) }}
        alarms={[{ id: 1, asset_id: 'CNC-04', metric: 'x', severity: 'critical', message: 'Spindle overheat', raised_at: '', state: 'active' }]}
        insights={[{ id: 'fault-CNC-04', severity: 'critical', category: 'Live condition', title: 'CNC-04 is in fault', detail: 'd', assetId: 'CNC-04' }]}
        workOrders={[]}
        pmPlans={[]}
        parts={[]}
      />,
    )
    expect(screen.getByText('Total assets').previousSibling).toHaveTextContent('29')
    expect(screen.getByText('Active alarms').previousSibling).toHaveTextContent('1')
    expect(screen.getByText('CNC-04 is in fault')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('Open work orders').previousSibling).toHaveTextContent('4'))
  })

  it('users page is clearly marked as demo data and cannot add users', () => {
    render(<UsersPage />)
    expect(screen.getByTestId('demo-banner')).toHaveTextContent('Demo data')
    expect(screen.getByRole('button', { name: /Add user/ })).toBeDisabled()
    fireEvent.click(screen.getByRole('tab', { name: /Roles/ }))
    expect(screen.getByText('Maintenance engineer')).toBeInTheDocument()
  })
})
