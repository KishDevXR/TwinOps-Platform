import type { LiveAssetTwin } from '../types/twin'

export const TYPE_LABEL: Record<string, string> = {
  cnc_machine: 'CNC machining centre',
  robot_cell: 'Robot cell',
  conveyor: 'Conveyor',
  centrifugal_pump: 'Centrifugal pump',
  air_compressor: 'Air compressor',
  chiller: 'Chiller',
  ahu: 'Air handling unit',
  energy_meter: 'Energy meter',
  forklift: 'Forklift',
  loading_dock: 'Loading dock',
}

/** Asset Library tabs. */
export const TYPE_GROUPS: { id: string; label: string; types: string[] }[] = [
  { id: 'machining', label: 'Machining', types: ['cnc_machine', 'robot_cell', 'conveyor'] },
  { id: 'utilities', label: 'Utilities', types: ['centrifugal_pump', 'air_compressor', 'chiller', 'ahu'] },
  { id: 'electrical', label: 'Electrical', types: ['energy_meter'] },
  { id: 'logistics', label: 'Logistics', types: ['forklift', 'loading_dock'] },
]

export const LINE_NAMES: Record<string, string> = {
  'LINE-01': 'Line 1 · Cylinder heads',
  'LINE-02': 'Line 2 · Gearbox casings',
  'LOG-01': 'Logistics',
}

/** An asset record as the asset service returns it. */
export interface AssetRecord {
  id: string
  name: string
  line_id: string
  type_id: string
  make: string
  model: string
  serial_no: string
  criticality: string
  lifecycle_state: string
  install_date: string | null
}

// The readings that matter most for each asset type.
const KEY_METRICS: Record<string, string[]> = {
  cnc_machine: ['spindle_temp_c', 'vibration_mm_s'],
  centrifugal_pump: ['flow_m3h', 'vibration_mm_s'],
  air_compressor: ['discharge_pressure_bar', 'motor_power_kw'],
  chiller: ['chilled_water_outlet_c', 'compressor_power_kw'],
  ahu: ['supply_air_temp_c', 'filter_dp_pa'],
  energy_meter: ['power_kw', 'power_factor'],
  robot_cell: ['cycle_time_s', 'power_kw'],
  conveyor: ['speed_m_min', 'motor_current_a'],
  forklift: ['battery_pct', 'load_kg'],
  loading_dock: ['pallets_pending', 'truck_dwell_s'],
}
const METRIC_LABEL: Record<string, string> = {
  spindle_temp_c: 'Spindle',
  vibration_mm_s: 'Vib',
  flow_m3h: 'Flow',
  discharge_pressure_bar: 'Pressure',
  motor_power_kw: 'Power',
  chilled_water_outlet_c: 'CHW out',
  compressor_power_kw: 'Power',
  supply_air_temp_c: 'Supply',
  filter_dp_pa: 'Filter dP',
  power_kw: 'Load',
  power_factor: 'PF',
  cycle_time_s: 'Cycle',
  speed_m_min: 'Speed',
  motor_current_a: 'Current',
  battery_pct: 'Battery',
  load_kg: 'Load',
  pallets_pending: 'Pallets',
  truck_dwell_s: 'Dwell',
}

export function fmtValue(v: number): string {
  if (Math.abs(v) >= 100) return Math.round(v).toLocaleString()
  return Number.isInteger(v) ? String(v) : v.toFixed(Math.abs(v) < 10 ? 2 : 1)
}

/** "Spindle 54.7 °C" style readings for an asset's key metrics, from its live twin. */
export function keyReadings(t: LiveAssetTwin | undefined): string[] {
  if (!t) return []
  return (KEY_METRICS[t.type_id] ?? []).flatMap((k) => {
    const m = t.metrics?.[k]
    if (!m || typeof m.v !== 'number') return []
    return [`${METRIC_LABEL[k] ?? k} ${fmtValue(m.v)}${m.unit ? ` ${m.unit}` : ''}`]
  })
}
