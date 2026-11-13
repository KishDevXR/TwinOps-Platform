import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AssetSidePanel } from '../components/AssetSidePanel'
import { PILOT_ASSETS_INITIAL } from '../constants/pilotAssets'
import type { AlarmItem } from '../types/twin'

describe('TC-TWN-04: 3D Asset Interaction and Side Panel', () => {
  const sampleAsset = { ...PILOT_ASSETS_INITIAL['CNC-01'], derived: { oee_pct: 88.5 } }
  const sampleAlarms: AlarmItem[] = [
    {
      id: 'ALM-1',
      asset_id: 'CNC-01',
      metric: 'spindle_temp_c',
      severity: 'high',
      message: 'CNC-01 high spindle temperature warning',
      raised_at: new Date().toISOString(),
      state: 'active',
    },
  ]

  it('renders asset side panel with live values, status badge, and line location', () => {
    const onClose = vi.fn()
    const onOpenSimulation = vi.fn()
    const onAcknowledge = vi.fn()

    render(
      <AssetSidePanel
        asset={sampleAsset}
        alarms={sampleAlarms}
        onClose={onClose}
        onOpenSimulation={onOpenSimulation}
        onAcknowledgeAlarm={onAcknowledge}
      />
    )

    // Verify Asset ID & Header
    expect(screen.getByTestId('panel-asset-id')).toHaveTextContent('CNC-01')
    expect(screen.getByTestId('panel-asset-name')).toHaveTextContent('CNC Machining Centre 01 (Roughing)')
    expect(screen.getByTestId('panel-asset-status')).toHaveTextContent('RUNNING')

    // Verify Live Metrics Tab
    expect(screen.getByTestId('metric-row-spindle_rpm')).toBeInTheDocument()
    expect(screen.getByTestId('metric-row-spindle_rpm')).toHaveTextContent(
      Number(sampleAsset.metrics.spindle_rpm.v).toFixed(2),
    )
    expect(screen.getByTestId('metric-row-spindle_rpm')).toHaveTextContent('RPM')

    // Switch to Derived KPIs Tab
    const kpiTabButton = screen.getByText('Derived KPIs')
    fireEvent.click(kpiTabButton)

    expect(screen.getByTestId('panel-kpis-tab')).toBeInTheDocument()
    expect(screen.getByTestId('kpi-row-oee_pct')).toHaveTextContent('88.5%')

    // Switch to Alarms Tab
    const alarmsTabButton = screen.getByText('Alarms')
    fireEvent.click(alarmsTabButton)

    expect(screen.getByText('CNC-01 high spindle temperature warning')).toBeInTheDocument()

    // Test Acknowledge button
    const ackButton = screen.getByText('Acknowledge')
    fireEvent.click(ackButton)
    expect(onAcknowledge).toHaveBeenCalledWith('ALM-1')

    // Test What-If trigger button
    const simButton = screen.getByTestId('btn-what-if-simulation')
    fireEvent.click(simButton)
    expect(onOpenSimulation).toHaveBeenCalledWith(sampleAsset)
  })
})
