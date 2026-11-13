import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Header } from '../components/Header'
import { LayerSelector } from '../components/LayerSelector'
import { AlarmTicker } from '../components/AlarmTicker'
import type { AlarmItem } from '../types/twin'

describe('TC-TWN-08 & Web UI Components', () => {
  it('Header shows site id, connection state, and alarm badge', () => {
    const onRefresh = vi.fn()
    const onOpenAlarms = vi.fn()

    render(
      <Header
        siteId="PUNE-01"
        connectionState="connected"
        lastLatencyMs={18}
        alarmCount={3}
        onRefresh={onRefresh}
        onOpenAlarms={onOpenAlarms}
      />
    )

    expect(screen.getByText('PUNE-01')).toBeInTheDocument()
    expect(screen.getByText('Live WS')).toBeInTheDocument()
    expect(screen.getByText('18ms')).toBeInTheDocument()
    expect(screen.getByTestId('alarm-badge')).toHaveTextContent('3')

    const refreshBtn = screen.getByLabelText('Refresh twin snapshot')
    fireEvent.click(refreshBtn)
    expect(onRefresh).toHaveBeenCalled()
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
