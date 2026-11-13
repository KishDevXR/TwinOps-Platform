import React, { useCallback, useState } from 'react'
import { Flame, RefreshCcw, Sliders, WifiOff } from 'lucide-react'
import { AlarmTicker } from '../components/AlarmTicker'
import { AssetSidePanel } from '../components/AssetSidePanel'
import { LayerSelector } from '../components/LayerSelector'
import { Scene3D } from '../components/PlantViewer3D/Scene3D'
import { TimelineScrubber } from '../components/TimelineScrubber'
import { WhatIfSimulationModal } from '../components/WhatIfSimulationModal'
import { navigate } from '../hooks/useHashRoute'
import type { AlarmItem, LiveAssetTwin, VisualizationLayer } from '../types/twin'

/** The live 3D plant: scene, layers, playback scrubber, asset side panel and test scenarios. */
export const PlantPage: React.FC<{
  assets: Record<string, LiveAssetTwin>
  selectedId: string | null
  alarms: AlarmItem[]
  onAcknowledge: (id: string | number) => void
  updateAssetOverride: (assetId: string, partial: Partial<LiveAssetTwin>) => void
  refetchSnapshot: () => void
}> = ({ assets, selectedId, alarms, onAcknowledge, updateAssetOverride, refetchSnapshot }) => {
  const [activeLayer, setActiveLayer] = useState<VisualizationLayer>('status')
  const [simulationAsset, setSimulationAsset] = useState<LiveAssetTwin | null>(null)
  const [isPlaybackMode, setIsPlaybackMode] = useState(false)
  const [selectedSpeed, setSelectedSpeed] = useState(10)
  const [showDemoToolbar, setShowDemoToolbar] = useState(false)
  const selectedAsset = selectedId ? (assets[selectedId] ?? null) : null
  const select = (id: string | null) => navigate(id ? { page: 'plant', id } : { page: 'plant' })

  // Historical scrubber (TC-TWN-06): colour the selected asset by its state at that time
  const handleScrubTime = useCallback(
    async (timestampIso: string) => {
      if (!selectedAsset) return
      try {
        const fromIso = new Date(new Date(timestampIso).getTime() - 60000).toISOString()
        const res = await fetch(
          `/api/v1/assets/${selectedAsset.asset_id}/playback?from=${encodeURIComponent(fromIso)}&to=${encodeURIComponent(timestampIso)}`,
        )
        if (res.ok) {
          const data = await res.json()
          const last = data?.points?.[data.points.length - 1]
          if (last) updateAssetOverride(selectedAsset.asset_id, { status: last.status, status_color: last.status_color })
        }
      } catch {
        // playback service unavailable: leave the live state
      }
    },
    [selectedAsset, updateAssetOverride],
  )

  // Viewer-only test scenarios (TC-TWN-03 / TC-TWN-08); the next live update overwrites them
  const injectOverheatCnc02 = () =>
    updateAssetOverride('CNC-02', {
      status: 'FAULT',
      status_color: 'red',
      metrics: { ...assets['CNC-02']?.metrics, spindle_temp_c: { v: 78.5, q: 0, unit: '°C' } },
      anomaly_score: 0.94,
    })
  const simulateOffline = (id: string) =>
    updateAssetOverride(id, { status: 'OFFLINE', status_color: 'grey', is_stale: true, anomaly_score: 0 })

  return (
    <div className="h-full flex flex-col">
      <AlarmTicker alarms={alarms} onSelectAlarmAsset={(id) => select(id)} onAcknowledge={onAcknowledge} />
      <div className="relative flex-1 overflow-hidden">
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20">
          <LayerSelector activeLayer={activeLayer} onChangeLayer={setActiveLayer} />
        </div>

        <div className="absolute top-4 right-4 z-20">
          <button
            onClick={() => setShowDemoToolbar(!showDemoToolbar)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/95 hover:bg-white border border-slate-200 text-xs text-blue-700 font-semibold shadow"
            data-testid="btn-demo-scenarios"
          >
            <Sliders className="w-3.5 h-3.5" /> Test scenarios
          </button>
          {showDemoToolbar && (
            <div className="mt-2 p-2.5 rounded-xl bg-white border border-slate-200 shadow-xl flex flex-col gap-1.5 min-w-[230px] text-xs">
              <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider px-1">Viewer-only, until next live update</div>
              <button onClick={injectOverheatCnc02} className="px-2 py-1.5 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 flex items-center gap-1.5 text-left" data-testid="btn-inject-overheat">
                <Flame className="w-3.5 h-3.5" /> TC-TWN-03: Overheat CNC-02
              </button>
              <button onClick={() => simulateOffline('CNC-04')} className="px-2 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 flex items-center gap-1.5 text-left" data-testid="btn-simulate-offline">
                <WifiOff className="w-3.5 h-3.5" /> TC-TWN-08: Stale CNC-04
              </button>
              <button onClick={refetchSnapshot} className="px-2 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 flex items-center gap-1.5 text-left">
                <RefreshCcw className="w-3.5 h-3.5" /> Reset to live state
              </button>
            </div>
          )}
        </div>

        <Scene3D assets={assets} selectedAssetId={selectedAsset?.asset_id ?? null} onSelectAsset={select} activeLayer={activeLayer} />

        <TimelineScrubber
          isPlaybackMode={isPlaybackMode}
          onTogglePlayback={setIsPlaybackMode}
          onScrubTime={handleScrubTime}
          selectedSpeed={selectedSpeed}
          onChangeSpeed={setSelectedSpeed}
        />

        {selectedAsset && (
          <AssetSidePanel
            asset={selectedAsset}
            alarms={alarms}
            onClose={() => select(null)}
            onOpenSimulation={setSimulationAsset}
            onAcknowledgeAlarm={onAcknowledge}
          />
        )}
        {simulationAsset && <WhatIfSimulationModal asset={simulationAsset} onClose={() => setSimulationAsset(null)} />}
      </div>
    </div>
  )
}
