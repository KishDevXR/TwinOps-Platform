import { describe, it, expect } from 'vitest'
import { mergeTwin } from '../hooks/useLiveTwin'
import { PILOT_ASSETS_INITIAL } from '../constants/pilotAssets'

// Shapes copied from services/twin/websocket_manager.py and the /sites/{id}/twin endpoint.
describe('TWN-02: viewer reads the twin service contract', () => {
  it('applies a flat twin_update: status, colour and metric value, keeping the unit', () => {
    const before = PILOT_ASSETS_INITIAL['CNC-03']
    const after = mergeTwin(before, {
      asset_id: 'CNC-03',
      status_color: 'red',
      operational_status: 'FAULT',
      last_updated: '2026-11-13T16:30:00+00:00',
      metrics: { spindle_temp_c: { v: 35.85, q: 0 } },
    })
    expect(after.status).toBe('FAULT')
    expect(after.status_color).toBe('red')
    expect(after.metrics.spindle_temp_c).toEqual({ v: 35.85, q: 0, unit: '°C' })
    expect(after.metrics.spindle_rpm).toEqual(before.metrics.spindle_rpm) // untouched
    expect(after.name).toBe(before.name)
    expect(after.position).toEqual(before.position)
    expect(after.is_stale).toBe(false)
  })

  it('maps snapshot fields (position_3d, derived_metrics) and treats grey as stale', () => {
    const after = mergeTwin(PILOT_ASSETS_INITIAL['FLT-01'], {
      asset_id: 'FLT-01',
      name: 'Forklift 01 (Inbound)',
      type_id: 'forklift',
      criticality: 'B',
      status_color: 'grey',
      operational_status: 'OFFLINE',
      position_3d: { x: 6, y: 0, z: 16.5, rot_y: 0 },
      derived_metrics: { utilisation_pct: 40 },
      metrics: { pos_x_m: { v: 3.5, q: 0 } },
    })
    expect(after.position).toEqual({ x: 6, y: 0, z: 16.5, rot_y: 0 })
    expect(after.derived.utilisation_pct).toBe(40)
    expect(after.metrics.pos_x_m.v).toBe(3.5)
    expect(after.is_stale).toBe(true)
  })
})
