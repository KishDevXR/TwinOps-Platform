// Plant layout in metres. Mirrors simulator/config.py (building 56 x 36, aisle at z = 16.5).
// x = west -> east, z = back wall -> front (camera side).

export const BUILDING = { w: 56, d: 36 }
export const AISLE_Z = 16.5
export const DOCK_Z = 9

export const PALETTE = {
  sky: '#e9ecf8',
  ground: '#dfe3f3',
  road: '#b7bddb',
  apron: '#cdd2ea',
  floor: '#f8f9fd',
  wall: '#ffffff',
  trim: '#3b5bdb',
  beam: '#f08c3a',
  box: '#e3b27a',
  line: '#f5c400',
  tree: '#35c26b',
  ink: '#5b6385',
}

export interface Zone {
  label: string
  x: number // centre
  z: number
  w: number
  d: number
  color: string
}

export const ZONES: Zone[] = [
  { label: 'RECEIVING', x: 6, z: 9, w: 10, d: 12, color: '#dbe4ff' },
  { label: 'LINE 01 · CYLINDER HEADS', x: 22, z: 8.5, w: 20, d: 9, color: '#e7f5ff' },
  { label: 'LINE 02 · GEARBOX CASINGS', x: 22, z: 24, w: 20, d: 9, color: '#e7f5ff' },
  { label: 'WASH & INSPECTION', x: 38, z: 16.5, w: 8, d: 24, color: '#f3f0ff' },
  { label: 'SHIPPING', x: 49, z: 9, w: 12, d: 12, color: '#d3f9d8' },
  { label: 'UTILITIES', x: 24, z: 33, w: 30, d: 5, color: '#fff3bf' },
  { label: 'MCC ROOM', x: 48, z: 33.5, w: 10, d: 4, color: '#ffe8cc' },
]

// Racks: [x, z, bays]. Raw castings by receiving, finished goods by shipping.
export const RACKS: [number, number, number][] = [
  [7, 2, 3],
  [7, 4.6, 3],
  [48, 2, 4],
  [48, 4.6, 4],
]

export const CHARGER = { x: 6, z: 28 }

// Dataset credits shown in the viewer (CC BY 4.0 requires attribution). See docs/DATASETS.md.
export const DATASET_CREDITS = [
  {
    title: 'AI4I 2020 Predictive Maintenance Dataset',
    usedFor: 'CNC machines',
    credit: 'S. Matzka (2020), UCI Machine Learning Repository. DOI 10.24432/C5HS5C',
    licence: 'CC BY 4.0',
  },
  {
    title: 'MetroPT-3 Dataset',
    usedFor: 'Air compressors',
    credit:
      'Davari, Veloso, Ribeiro & Gama (2021), UCI Machine Learning Repository. DOI 10.24432/C5VW3R',
    licence: 'CC BY 4.0',
  },
  {
    title: 'Condition Monitoring of Hydraulic Systems',
    usedFor: 'Coolant pumps',
    credit:
      'Helwig, Pignanelli & Schütze (2015), UCI Machine Learning Repository. DOI 10.24432/C5CW21',
    licence: 'CC BY 4.0',
  },
]
