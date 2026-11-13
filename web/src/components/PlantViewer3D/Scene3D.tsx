import React, { useState, useRef } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Html } from '@react-three/drei'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import type { LiveAssetTwin, VisualizationLayer } from '../../types/twin'
import { FactoryFloor } from './FactoryFloor'
import { MachineMesh } from './ParametricMeshes'
import { Camera, Eye, Layers } from 'lucide-react'

interface Scene3DProps {
  assets: Record<string, LiveAssetTwin>
  selectedAssetId: string | null
  onSelectAsset: (assetId: string) => void
  activeLayer: VisualizationLayer
}

export const Scene3D: React.FC<Scene3DProps> = ({
  assets,
  selectedAssetId,
  onSelectAsset,
  activeLayer,
}) => {
  const [hoveredAssetId, setHoveredAssetId] = useState<string | null>(null)
  const controlsRef = useRef<OrbitControlsImpl>(null)

  const hoveredAsset = hoveredAssetId ? assets[hoveredAssetId] : null

  // Camera preset handler
  const setCameraPreset = (view: 'overview' | 'line1' | 'line2' | 'utilities' | 'top') => {
    if (!controlsRef.current) return
    const controls = controlsRef.current

    switch (view) {
      case 'overview':
        controls.object.position.set(22, 24, 38)
        controls.target.set(12, 1, 14)
        break
      case 'line1':
        controls.object.position.set(12, 12, 16)
        controls.target.set(12, 1, 6)
        break
      case 'line2':
        controls.object.position.set(12, 12, 32)
        controls.target.set(12, 1, 21)
        break
      case 'utilities':
        controls.object.position.set(8, 10, 20)
        controls.target.set(8, 1, 12)
        break
      case 'top':
        controls.object.position.set(12, 45, 14.1)
        controls.target.set(12, 0, 14)
        break
    }
    controls.update()
  }

  return (
    <div className="relative w-full h-full bg-slate-950 overflow-hidden select-none" data-testid="scene-3d-container">
      {/* 3D Canvas */}
      <Canvas
        shadows
        camera={{ position: [22, 24, 38], fov: 45 }}
        gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
        dpr={[1, 2]}
      >
        {/* Lights */}
        <ambientLight intensity={0.6} />
        <directionalLight
          position={[25, 40, 20]}
          intensity={1.2}
          castShadow
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
          shadow-camera-far={80}
          shadow-camera-left={-25}
          shadow-camera-right={25}
          shadow-camera-top={25}
          shadow-camera-bottom={-25}
        />
        <pointLight position={[10, 8, 10]} intensity={0.5} color="#38bdf8" />
        <pointLight position={[10, 8, 22]} intensity={0.5} color="#38bdf8" />

        {/* Factory Floor */}
        <FactoryFloor />

        {/* 25 Asset Meshes */}
        {Object.values(assets).map((asset) => (
          <MachineMesh
            key={asset.asset_id}
            asset={asset}
            activeLayer={activeLayer}
            isSelected={selectedAssetId === asset.asset_id}
            isHovered={hoveredAssetId === asset.asset_id}
            onPointerOver={(e) => {
              e.stopPropagation()
              setHoveredAssetId(asset.asset_id)
            }}
            onPointerOut={() => {
              setHoveredAssetId((curr) => (curr === asset.asset_id ? null : curr))
            }}
            onClick={(e) => {
              e.stopPropagation()
              onSelectAsset(asset.asset_id)
            }}
          />
        ))}

        {/* 3D Tooltip for Hovered Asset */}
        {hoveredAsset && (
          <Html
            position={[
              hoveredAsset.position.x,
              hoveredAsset.position.y + 3.2,
              hoveredAsset.position.z,
            ]}
            center
            distanceFactor={24}
          >
            <div
              className="pointer-events-none px-3 py-2 rounded-lg bg-slate-900/95 border border-slate-700 text-white shadow-2xl text-xs backdrop-blur-md min-w-[160px]"
              data-testid="asset-3d-tooltip"
            >
              <div className="flex items-center justify-between gap-2 border-b border-slate-800 pb-1 mb-1 font-semibold">
                <span className="text-sky-400">{hoveredAsset.asset_id}</span>
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                    hoveredAsset.status_color === 'green'
                      ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                      : hoveredAsset.status_color === 'red'
                      ? 'bg-rose-950 text-rose-400 border border-rose-800 animate-pulse'
                      : hoveredAsset.status_color === 'amber'
                      ? 'bg-amber-950 text-amber-400 border border-amber-800'
                      : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  {hoveredAsset.status}
                </span>
              </div>
              <div className="text-slate-300 truncate mb-1">{hoveredAsset.name}</div>
              <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-[11px] text-slate-400">
                {Object.entries(hoveredAsset.metrics)
                  .slice(0, 3)
                  .map(([k, m]) => (
                    <div key={k} className="flex justify-between">
                      <span className="truncate">{k.split('_')[0]}:</span>
                      <span className="text-slate-200 font-mono ml-1">
                        {typeof m.v === 'number' ? m.v.toFixed(1) : m.v} {m.unit || ''}
                      </span>
                    </div>
                  ))}
              </div>
              <div className="mt-1 pt-1 border-t border-slate-800/80 text-[10px] text-sky-400/80 text-right">
                Click to inspect →
              </div>
            </div>
          </Html>
        )}

        <OrbitControls
          ref={controlsRef}
          makeDefault
          maxPolarAngle={Math.PI / 2.05}
          minDistance={4}
          maxDistance={70}
          dampingFactor={0.08}
        />
      </Canvas>

      {/* Floating 3D Navigation Controls Toolbar */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-1.5 bg-slate-900/90 border border-slate-800 rounded-lg p-1.5 backdrop-blur-md shadow-lg text-xs text-slate-300">
        <span className="flex items-center gap-1 px-2 font-medium text-slate-400 border-r border-slate-800">
          <Camera className="w-3.5 h-3.5 text-sky-400" /> Presets
        </span>
        <button
          onClick={() => setCameraPreset('overview')}
          className="px-2.5 py-1 rounded hover:bg-slate-800 hover:text-white transition flex items-center gap-1"
          title="Full plant view"
        >
          <Eye className="w-3 h-3" /> Overview
        </button>
        <button
          onClick={() => setCameraPreset('line1')}
          className="px-2.5 py-1 rounded hover:bg-slate-800 hover:text-white transition"
          title="Line 1 Machining bay"
        >
          Line 1
        </button>
        <button
          onClick={() => setCameraPreset('line2')}
          className="px-2.5 py-1 rounded hover:bg-slate-800 hover:text-white transition"
          title="Line 2 Machining bay"
        >
          Line 2
        </button>
        <button
          onClick={() => setCameraPreset('utilities')}
          className="px-2.5 py-1 rounded hover:bg-slate-800 hover:text-white transition"
          title="Utilities corridor"
        >
          Utilities
        </button>
        <button
          onClick={() => setCameraPreset('top')}
          className="px-2.5 py-1 rounded hover:bg-slate-800 hover:text-white transition"
          title="Top-down 2D floorplan view"
        >
          Top Down
        </button>
      </div>

      {/* Legend Pill */}
      <div className="absolute bottom-4 left-4 z-10 flex items-center gap-3 bg-slate-900/90 border border-slate-800 rounded-lg px-3 py-1.5 backdrop-blur-md text-xs text-slate-300">
        <span className="flex items-center gap-1 text-slate-400 font-medium">
          <Layers className="w-3.5 h-3.5 text-sky-400" /> Legend:
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50" />
          Running
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500 shadow-sm shadow-amber-500/50" />
          Warning / Idle
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-500 shadow-sm shadow-rose-500/50 animate-pulse" />
          Alarm / Fault
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-slate-500" />
          Offline / Stale
        </span>
      </div>
    </div>
  )
}
