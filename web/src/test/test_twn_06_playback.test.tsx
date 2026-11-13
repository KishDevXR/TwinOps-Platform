import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TimelineScrubber } from '../components/TimelineScrubber'

describe('TC-TWN-06: Historical Playback Scrubber', () => {
  it('toggles playback mode and allows speed selection and slider scrubbing', () => {
    const onTogglePlayback = vi.fn()
    const onScrubTime = vi.fn()
    const onChangeSpeed = vi.fn()

    const { rerender } = render(
      <TimelineScrubber
        isPlaybackMode={false}
        onTogglePlayback={onTogglePlayback}
        onScrubTime={onScrubTime}
        selectedSpeed={10}
        onChangeSpeed={onChangeSpeed}
      />
    )

    // Button to switch to playback
    const toggleBtn = screen.getByTestId('btn-toggle-playback')
    expect(toggleBtn).toHaveTextContent('SWITCH TO PLAYBACK')

    fireEvent.click(toggleBtn)
    expect(onTogglePlayback).toHaveBeenCalledWith(true)

    // Re-render in playback mode
    rerender(
      <TimelineScrubber
        isPlaybackMode={true}
        onTogglePlayback={onTogglePlayback}
        onScrubTime={onScrubTime}
        selectedSpeed={10}
        onChangeSpeed={onChangeSpeed}
      />
    )

    expect(screen.getByTestId('btn-toggle-playback')).toHaveTextContent('PLAYBACK ACTIVE')
    expect(screen.getByTestId('btn-play-pause')).toBeInTheDocument()
    expect(screen.getByTestId('scrubber-slider')).toBeInTheDocument()

    // Test speed button 10x and 60x
    const speed60xBtn = screen.getByTestId('speed-btn-60x')
    fireEvent.click(speed60xBtn)
    expect(onChangeSpeed).toHaveBeenCalledWith(60)

    // Move slider
    const slider = screen.getByTestId('scrubber-slider')
    fireEvent.change(slider, { target: { value: '50' } })
    expect(onScrubTime).toHaveBeenCalled()
  })
})
