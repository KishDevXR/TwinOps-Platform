import { describe, it, expect } from 'vitest'
import { getLayerColor } from '../components/PlantViewer3D/ParametricMeshes'
import { PILOT_ASSETS_INITIAL } from '../constants/pilotAssets'
import type { LiveAssetTwin } from '../types/twin'

describe('TC-TWN-03: 3D Status Colors and Visualization Layers', () => {
  it('returns appropriate hex codes for running green, warning amber, alarm red, and offline grey', () => {
    const baseAsset = PILOT_ASSETS_INITIAL['CNC-01']

    const greenAsset: LiveAssetTwin = { ...baseAsset, status_color: 'green' }
    const amberAsset: LiveAssetTwin = { ...baseAsset, status_color: 'amber' }
    const redAsset: LiveAssetTwin = { ...baseAsset, status_color: 'red' }
    const greyAsset: LiveAssetTwin = { ...baseAsset, status_color: 'grey' }

    expect(getLayerColor(greenAsset, 'status')).toBe('#22c55e')
    expect(getLayerColor(amberAsset, 'status')).toBe('#f59e0b')
    expect(getLayerColor(redAsset, 'status')).toBe('#ef4444')
    expect(getLayerColor(greyAsset, 'status')).toBe('#64748b')
  })

  it('computes energy heatmap gradient based on power_kw consumption', () => {
    const baseAsset = PILOT_ASSETS_INITIAL['EM-01'] // ~118 kW

    // Very high power (> 100 kW) -> Red
    expect(getLayerColor(baseAsset, 'energy')).toBe('#ef4444')

    // Moderate power (12 kW) -> Yellow
    const cncAsset = PILOT_ASSETS_INITIAL['CNC-01']
    expect(getLayerColor(cncAsset, 'energy')).toBe('#eab308')

    // Low power conveyor (3.2 kW) -> Cyan
    const convAsset = PILOT_ASSETS_INITIAL['CONV-01']
    expect(getLayerColor(convAsset, 'energy')).toBe('#06b6d4')
  })

  it('computes anomaly health gradient based on anomaly risk score', () => {
    const baseAsset = PILOT_ASSETS_INITIAL['CNC-01']

    const normalAsset: LiveAssetTwin = { ...baseAsset, anomaly_score: 0.05 }
    const warningAsset: LiveAssetTwin = { ...baseAsset, anomaly_score: 0.65 }
    const criticalAsset: LiveAssetTwin = { ...baseAsset, anomaly_score: 0.92 }

    expect(getLayerColor(normalAsset, 'anomaly')).toBe('#10b981')
    expect(getLayerColor(warningAsset, 'anomaly')).toBe('#f59e0b')
    expect(getLayerColor(criticalAsset, 'anomaly')).toBe('#dc2626')
  })
})
