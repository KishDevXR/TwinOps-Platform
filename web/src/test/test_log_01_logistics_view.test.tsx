import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LogisticsHud } from '../components/PlantViewer3D/Logistics'
import { assetXZ } from '../components/PlantViewer3D/ParametricMeshes'
import { PILOT_ASSETS_INITIAL } from '../constants/pilotAssets'
import { BUILDING } from '../constants/plantLayout'
import type { LiveAssetTwin } from '../types/twin'

const withMetrics = (id: string, values: Record<string, number>): LiveAssetTwin => {
  const a = PILOT_ASSETS_INITIAL[id]
  const metrics = { ...a.metrics }
  for (const [k, v] of Object.entries(values)) metrics[k] = { ...metrics[k], v }
  return { ...a, metrics }
}

describe('LOG-01: logistics in the plant viewer', () => {
  it('ships all 29 pilot assets, every one placed inside the building', () => {
    const assets = Object.values(PILOT_ASSETS_INITIAL)
    expect(assets).toHaveLength(29)
    for (const a of assets) {
      const [x, z] = assetXZ(a)
      expect(x).toBeGreaterThanOrEqual(0)
      expect(x).toBeLessThanOrEqual(BUILDING.w)
      expect(z).toBeGreaterThanOrEqual(0)
      expect(z).toBeLessThanOrEqual(BUILDING.d)
    }
  })

  it('draws a forklift at its live reported position, not its home position', () => {
    const f = withMetrics('FLT-01', { pos_x_m: 11, pos_z_m: 24 })
    expect(assetXZ(f)).toEqual([11, 24])
    expect(assetXZ(PILOT_ASSETS_INITIAL['CNC-01'])).toEqual([16, 9])
  })

  it('shows dock and forklift state in the HUD', () => {
    const assets = {
      ...PILOT_ASSETS_INITIAL,
      'DOCK-RCV': withMetrics('DOCK-RCV', { truck_present: 1, truck_dwell_s: 42, pallets_pending: 3, pallets_handled: 9 }),
      'DOCK-SHP': withMetrics('DOCK-SHP', { truck_present: 0, pallets_pending: 2, pallets_handled: 12 }),
      'FLT-01': withMetrics('FLT-01', { load_kg: 450, battery_pct: 87.4, pallets_moved: 5 }),
    }
    render(<LogisticsHud assets={assets} />)
    const hud = screen.getByTestId('logistics-hud')
    expect(hud).toHaveTextContent('Truck docked · 42 s')
    expect(hud).toHaveTextContent('3 to unload · 9 received')
    expect(hud).toHaveTextContent('2 staged · 12 shipped')
    expect(hud).toHaveTextContent('Carrying pallet')
    expect(hud).toHaveTextContent('Battery 87% · 5 moved')
  })
})
