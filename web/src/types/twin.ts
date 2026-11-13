export type StatusColor = 'green' | 'amber' | 'red' | 'grey'

export type VisualizationLayer = 'status' | 'energy' | 'anomaly'

export interface AssetPosition {
  x: number
  y: number
  z: number
  rot_y?: number
  rotY?: number
}

export interface MetricValue {
  v: number
  q: number
  unit?: string
}

export interface LiveAssetTwin {
  asset_id: string
  name: string
  type_id: string
  status: string
  status_color: StatusColor
  line_id: string
  criticality: string
  position: AssetPosition
  metrics: Record<string, MetricValue>
  derived: Record<string, number>
  last_seen: string
  is_stale: boolean
  anomaly_score?: number
}

export interface AlarmItem {
  id: string | number
  asset_id: string
  metric: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  message: string
  value?: number
  raised_at: string
  state: 'active' | 'acked' | 'cleared'
}

export interface SimulationResult {
  asset_id: string
  inputs: Record<string, number>
  predicted_metrics: Record<string, number>
  predicted_kpis: Record<string, number>
  predicted_rul_hours: number
  health_index: number
  deltas?: Record<string, number>
}

export interface PlaybackDataPoint {
  ts: string
  values: Record<string, number>
  status: string
  status_color: StatusColor
}
