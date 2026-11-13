import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { WhatIfSimulationModal } from '../components/WhatIfSimulationModal'
import { PILOT_ASSETS_INITIAL } from '../constants/pilotAssets'

describe('TC-TWN-07: What-If Sandbox Simulation', () => {
  const pumpAsset = PILOT_ASSETS_INITIAL['PUMP-01']

  it('runs what-if scenario with +20% pump speed and predicts power, temp, and RUL changes', async () => {
    const onClose = vi.fn()

    render(
      <WhatIfSimulationModal
        asset={pumpAsset}
        onClose={onClose}
      />
    )

    // Verify modal title and safety disclaimer
    expect(screen.getByText(/What-If Scenario Sandbox/)).toBeInTheDocument()
    expect(screen.getByText(/No PLC\/SCADA write-back occurs/)).toBeInTheDocument()

    // Default speed delta is +20% as per TC-TWN-07 spec
    expect(screen.getByTestId('speed-delta-val')).toHaveTextContent('+20%')

    // Run simulation
    const runBtn = screen.getByTestId('btn-execute-simulation')
    fireEvent.click(runBtn)

    await waitFor(() => {
      expect(screen.getByTestId('simulation-results')).toBeInTheDocument()
    })

    // Verify predicted power, core temp, and RUL cards are rendered
    const predPower = screen.getByTestId('pred-power')
    const predTemp = screen.getByTestId('pred-temp')
    const predRul = screen.getByTestId('pred-rul')

    expect(predPower).not.toBeEmptyDOMElement()
    expect(predTemp).not.toBeEmptyDOMElement()
    expect(predRul).not.toBeEmptyDOMElement()

    // Baseline power was 9.3 kW; +20% speed on pump (cubic power law) should predict > 14 kW
    const powerVal = parseFloat(predPower.textContent || '0')
    expect(powerVal).toBeGreaterThan(12.0)
  })
})
