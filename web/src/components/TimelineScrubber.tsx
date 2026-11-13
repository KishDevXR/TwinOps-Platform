import React, { useState, useEffect, useRef } from 'react'
import { Play, Pause, RotateCcw, Clock } from 'lucide-react'

interface TimelineScrubberProps {
  isPlaybackMode: boolean
  onTogglePlayback: (enabled: boolean) => void
  onScrubTime: (timestampIso: string) => void
  selectedSpeed: number
  onChangeSpeed: (speed: number) => void
}

export const TimelineScrubber: React.FC<TimelineScrubberProps> = ({
  isPlaybackMode,
  onTogglePlayback,
  onScrubTime,
  selectedSpeed,
  onChangeSpeed,
}) => {
  const [isPlaying, setIsPlaying] = useState<boolean>(false)
  const [progressPct, setProgressPct] = useState<number>(100)
  const intervalRef = useRef<any>(null)

  // 1 hour window
  const ONE_HOUR_MS = 60 * 60 * 1000

  useEffect(() => {
    if (!isPlaybackMode) {
      setIsPlaying(false)
      setProgressPct(100)
      if (intervalRef.current) clearInterval(intervalRef.current)
      return
    }

    if (isPlaying) {
      intervalRef.current = setInterval(() => {
        setProgressPct((prev) => {
          if (prev >= 100) {
            setIsPlaying(false)
            return 100
          }
          const step = (100 / (3600 / selectedSpeed)) * 0.1
          const next = Math.min(100, prev + step)
          return next
        })
      }, 100)
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [isPlaying, isPlaybackMode, selectedSpeed])

  useEffect(() => {
    if (isPlaybackMode) {
      const now = Date.now()
      const targetTime = new Date(now - ONE_HOUR_MS + (progressPct / 100) * ONE_HOUR_MS).toISOString()
      onScrubTime(targetTime)
    }
  }, [progressPct, isPlaybackMode, onScrubTime])

  const currentScrubDate = new Date(
    Date.now() - ONE_HOUR_MS + (progressPct / 100) * ONE_HOUR_MS
  )

  return (
    <div
      className="absolute bottom-4 right-4 z-20 flex items-center gap-3 bg-slate-900/95 border border-slate-800 rounded-xl px-4 py-2.5 backdrop-blur-md shadow-2xl text-xs text-slate-200 select-none min-w-[520px]"
      data-testid="timeline-scrubber"
    >
      {/* Mode toggle button */}
      <button
        onClick={() => {
          const next = !isPlaybackMode
          onTogglePlayback(next)
          if (next) {
            setProgressPct(0)
            setIsPlaying(true)
          }
        }}
        className={`px-3 py-1.5 rounded-lg font-bold transition flex items-center gap-1.5 ${
          isPlaybackMode
            ? 'bg-amber-500 text-slate-950 shadow-md'
            : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
        }`}
        data-testid="btn-toggle-playback"
      >
        <Clock className="w-3.5 h-3.5" />
        {isPlaybackMode ? 'PLAYBACK ACTIVE' : 'SWITCH TO PLAYBACK'}
      </button>

      {isPlaybackMode && (
        <>
          {/* Play/Pause */}
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white transition"
            aria-label={isPlaying ? 'Pause' : 'Play'}
            data-testid="btn-play-pause"
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-white" />}
          </button>

          {/* Reset/Rewind */}
          <button
            onClick={() => {
              setProgressPct(0)
              setIsPlaying(true)
            }}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
            title="Rewind to -1h"
            aria-label="Rewind"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          {/* Scrubber slider */}
          <div className="flex-1 flex flex-col gap-1">
            <input
              type="range"
              min="0"
              max="100"
              step="0.5"
              value={progressPct}
              onChange={(e) => {
                setProgressPct(parseFloat(e.target.value))
                setIsPlaying(false)
              }}
              className="w-full accent-sky-500 cursor-pointer h-1.5 bg-slate-700 rounded-lg"
              data-testid="scrubber-slider"
            />
            <div className="flex justify-between text-[10px] text-slate-400 font-mono">
              <span>-60m</span>
              <span className="text-sky-400 font-semibold">
                {currentScrubDate.toLocaleTimeString()}
              </span>
              <span>NOW</span>
            </div>
          </div>

          {/* Speed Selector */}
          <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-0.5 border border-slate-700">
            {[1, 5, 10, 60].map((spd) => (
              <button
                key={spd}
                onClick={() => onChangeSpeed(spd)}
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold transition ${
                  selectedSpeed === spd
                    ? 'bg-sky-500 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
                data-testid={`speed-btn-${spd}x`}
              >
                {spd}x
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
