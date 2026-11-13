import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Topbar } from '../components/layout/AppShell'
import { LayerSelector } from '../components/LayerSelector'
import { AlarmTicker } from '../components/AlarmTicker'
import type { AlarmItem } from '../types/twin'

describe('TC-TWN-08 & Web UI Components', () => {
  it('Topbar shows connection state, latency and the active alarm count', () => {
    const onRefresh = vi.fn()
    const { rerender } = render(
      <Topbar connectionState="connected" lastLatencyMs={18} alarmCount={3} onRefresh={onRefresh} />
    )
    expect(screen.getByTestId('connection-state')).toHaveTextContent('Live · 18ms')
    expect(screen.getByTestId('alarm-badge')).toHaveTextContent('3')
    fireEvent.click(screen.getByLabelText('Refresh twin snapshot'))
    expect(onRefresh).toHaveBeenCalled()

    rerender(<Topbar connectionState="disconnected" lastLatencyMs={18} alarmCount={0} onRefresh={onRefresh} />)
    expect(screen.getByTestId('connection-state')).toHaveTextContent('Offline')
    expect(screen.queryByTestId('alarm-badge')).toBeNull()
  })

  it('LayerSelector switches active layer between status, energy, and anomaly', () => {
    const onChangeLayer = vi.fn()

    render(
      <LayerSelector
        activeLayer="status"
        onChangeLayer={onChangeLayer}
      />
    )

    const energyBtn = screen.getByTestId('layer-btn-energy')
    fireEvent.click(energyBtn)
    expect(onChangeLayer).toHaveBeenCalledWith('energy')

    const anomalyBtn = screen.getByTestId('layer-btn-anomaly')
    fireEvent.click(anomalyBtn)
    expect(onChangeLayer).toHaveBeenCalledWith('anomaly')
  })

  it('AlarmTicker shows alert items and allows acknowledgment', () => {
    const alarms: AlarmItem[] = [
      {
        id: 'ALM-99',
        asset_id: 'CNC-02',
        metric: 'spindle_temp_c',
        severity: 'critical',
        message: 'CNC-02 Overheat detected',
        raised_at: new Date().toISOString(),
        state: 'active',
      },
    ]

    const onSelectAsset = vi.fn()
    const onAck = vi.fn()

    render(
      <AlarmTicker
        alarms={alarms}
        onSelectAlarmAsset={onSelectAsset}
        onAcknowledge={onAck}
      />
    )

    expect(screen.getByTestId('alarm-ticker')).toBeInTheDocument()
    expect(screen.getByText('CNC-02 Overheat detected')).toBeInTheDocument()

    const ackBtn = screen.getByText('Ack')
    fireEvent.click(ackBtn)
    expect(onAck).toHaveBeenCalledWith('ALM-99')
  })
})
