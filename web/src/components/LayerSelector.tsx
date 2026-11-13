import React from 'react'
import type { VisualizationLayer } from '../types/twin'
import { Activity, Zap, ShieldAlert } from 'lucide-react'

interface LayerSelectorProps {
  activeLayer: VisualizationLayer
  onChangeLayer: (layer: VisualizationLayer) => void
}

export const LayerSelector: React.FC<LayerSelectorProps> = ({
  activeLayer,
  onChangeLayer,
}) => {
  return (
    <div className="flex items-center gap-1 bg-slate-900/90 border border-slate-800 rounded-lg p-1 backdrop-blur-md shadow-lg text-xs">
      <button
        onClick={() => onChangeLayer('status')}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition ${
          activeLayer === 'status'
            ? 'bg-sky-500 text-white shadow-sm'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
        }`}
        data-testid="layer-btn-status"
      >
        <Activity className="w-3.5 h-3.5" />
        Status
      </button>

      <button
        onClick={() => onChangeLayer('energy')}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition ${
          activeLayer === 'energy'
            ? 'bg-amber-500 text-white shadow-sm'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
        }`}
        data-testid="layer-btn-energy"
      >
        <Zap className="w-3.5 h-3.5" />
        Energy Heatmap
      </button>

      <button
        onClick={() => onChangeLayer('anomaly')}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition ${
          activeLayer === 'anomaly'
            ? 'bg-purple-500 text-white shadow-sm'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
        }`}
        data-testid="layer-btn-anomaly"
      >
        <ShieldAlert className="w-3.5 h-3.5" />
        Anomaly Health
      </button>
    </div>
  )
}
