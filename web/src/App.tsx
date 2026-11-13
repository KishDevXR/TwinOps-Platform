import { useState, useCallback } from 'react'
import { useLiveTwin } from './hooks/useLiveTwin'
import { Header } from './components/Header'
import { AlarmTicker } from './components/AlarmTicker'
import { LayerSelector } from './components/LayerSelector'
import { AssetSidePanel } from './components/AssetSidePanel'
import { TimelineScrubber } from './components/TimelineScrubber'
import { WhatIfSimulationModal } from './components/WhatIfSimulationModal'
import { Scene3D } from './components/PlantViewer3D/Scene3D'
import type { VisualizationLayer, LiveAssetTwin } from './types/twin'
import { Sliders, Flame, WifiOff, RefreshCcw } from 'lucide-react'

export function App() {
  const {
    assets,
    selectedAsset,
    setSelectedAssetId,
    connectionState,
    lastLatencyMs,
    alarms,
    acknowledgeAlarm,
    updateAssetOverride,
    refetchSnapshot,
  } = useLiveTwin({ siteId: 'PUNE-01' })

  const [activeLayer, setActiveLayer] = useState<VisualizationLayer>('status')
  const [simulationAsset, setSimulationAsset] = useState<LiveAssetTwin | null>(null)
  const [isPlaybackMode, setIsPlaybackMode] = useState<boolean>(false)
  const [selectedSpeed, setSelectedSpeed] = useState<number>(10)
  const [showDemoToolbar, setShowDemoToolbar] = useState<boolean>(false)

  // Handle Historical Scrubber Time Change (TC-TWN-06)
  const handleScrubTime = useCallback(async (timestampIso: string) => {
    // When playback mode is enabled, interpolate/fetch playback states
    if (selectedAsset) {
      try {
        const fromIso = new Date(new Date(timestampIso).getTime() - 60000).toISOString()
        const res = await fetch(
          `/api/v1/assets/${selectedAsset.asset_id}/playback?from=${encodeURIComponent(
            fromIso
          )}&to=${encodeURIComponent(timestampIso)}`
        )
        if (res.ok) {
          const data = await res.json()
          if (data && data.points && data.points.length > 0) {
            const lastPt = data.points[data.points.length - 1]
            updateAssetOverride(selectedAsset.asset_id, {
              status: lastPt.status,
              status_color: lastPt.status_color,
            })
          }
        }
      } catch {
        // Mock historical variation if offline
      }
    }
  }, [selectedAsset, updateAssetOverride])

  // Demo Fault Injection Helpers (TC-TWN-03 & TC-TWN-08)
  const injectOverheatCnc02 = () => {
    updateAssetOverride('CNC-02', {
      status: 'FAULT',
      status_color: 'red',
      metrics: {
        ...assets['CNC-02']?.metrics,
        spindle_temp_c: { v: 78.5, q: 0, unit: '°C' },
      },
      anomaly_score: 0.94,
    })
  }

  const simulateOfflineStaleAsset = (assetId: string) => {
    updateAssetOverride(assetId, {
      status: 'OFFLINE',
      status_color: 'grey',
      is_stale: true,
      anomaly_score: 0.0,
    })
  }

  const resetAllNominal = () => {
    refetchSnapshot()
  }

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Top Header */}
      <Header
        siteId="PUNE-01"
        connectionState={connectionState}
        lastLatencyMs={lastLatencyMs}
        alarmCount={alarms.filter((a) => a.state === 'active').length}
        onRefresh={refetchSnapshot}
        onOpenAlarms={() => {
          if (selectedAsset) {
            // Already shows alarms tab in side panel
          }
        }}
      />

      {/* Alarm Ticker Banner */}
      <AlarmTicker
        alarms={alarms}
        onSelectAlarmAsset={(id) => setSelectedAssetId(id)}
        onAcknowledge={acknowledgeAlarm}
      />

      {/* Main 3D Canvas Area */}
      <main className="relative flex-1 w-full h-full overflow-hidden">
        {/* Layer Selector in Top Center */}
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20">
          <LayerSelector
            activeLayer={activeLayer}
            onChangeLayer={(l) => setActiveLayer(l)}
          />
        </div>

        {/* Demo Test Scenario Drawer Trigger */}
        <div className="absolute top-4 right-4 z-20">
          <button
            onClick={() => setShowDemoToolbar(!showDemoToolbar)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900/90 hover:bg-slate-800 border border-slate-800 backdrop-blur-md text-xs text-sky-400 font-medium transition shadow-lg"
            data-testid="btn-demo-scenarios"
          >
            <Sliders className="w-3.5 h-3.5" />
            Test Scenarios
          </button>

          {showDemoToolbar && (
            <div className="mt-2 p-2.5 rounded-xl bg-slate-900/95 border border-slate-800 shadow-2xl backdrop-blur-md flex flex-col gap-1.5 min-w-[220px] text-xs">
              <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider px-1">
                PRD Test Scenarios
              </div>
              <button
                onClick={injectOverheatCnc02}
                className="px-2 py-1.5 rounded bg-rose-950/60 hover:bg-rose-900/80 border border-rose-800/80 text-rose-300 flex items-center gap-1.5 text-left transition"
                data-testid="btn-inject-overheat"
              >
                <Flame className="w-3.5 h-3.5 text-rose-400" />
                TC-TWN-03: Overheat CNC-02 (Red)
              </button>
              <button
                onClick={() => simulateOfflineStaleAsset('CNC-04')}
                className="px-2 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center gap-1.5 text-left transition"
                data-testid="btn-simulate-offline"
              >
                <WifiOff className="w-3.5 h-3.5 text-slate-400" />
                TC-TWN-08: Stale CNC-04 (Grey)
              </button>
              <button
                onClick={resetAllNominal}
                className="px-2 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center gap-1.5 text-left transition"
              >
                <RefreshCcw className="w-3.5 h-3.5 text-sky-400" />
                Reset Nominal State
              </button>
            </div>
          )}
        </div>

        {/* 3D Scene View */}
        <Scene3D
          assets={assets}
          selectedAssetId={selectedAsset?.asset_id || null}
          onSelectAsset={(id) => setSelectedAssetId(id)}
          activeLayer={activeLayer}
        />

        {/* Timeline Scrubber for Playback */}
        <TimelineScrubber
          isPlaybackMode={isPlaybackMode}
          onTogglePlayback={setIsPlaybackMode}
          onScrubTime={handleScrubTime}
          selectedSpeed={selectedSpeed}
          onChangeSpeed={setSelectedSpeed}
        />

        {/* Asset Detail Drawer Panel (TC-TWN-04) */}
        {selectedAsset && (
          <AssetSidePanel
            asset={selectedAsset}
            alarms={alarms}
            onClose={() => setSelectedAssetId(null)}
            onOpenSimulation={(ast) => setSimulationAsset(ast)}
            onAcknowledgeAlarm={acknowledgeAlarm}
          />
        )}

        {/* What-If Simulation Sandbox Modal (TC-TWN-07) */}
        {simulationAsset && (
          <WhatIfSimulationModal
            asset={simulationAsset}
            onClose={() => setSimulationAsset(null)}
          />
        )}
      </main>
    </div>
  )
}

export default App
