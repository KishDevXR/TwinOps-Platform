import React, { useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { Truck as TruckIcon, Forklift, PackageCheck } from 'lucide-react'
import type { LiveAssetTwin } from '../../types/twin'
import { BUILDING, DOCK_Z, PALETTE as P } from '../../constants/plantLayout'

const num = (a: LiveAssetTwin | undefined, metric: string) => Number(a?.metrics?.[metric]?.v) || 0

/** Truck that pulls in from the perimeter road while its dock reports truck_present. */
const Truck: React.FC<{ dock?: LiveAssetTwin; side: 'west' | 'east'; color: string }> = ({ dock, side, color }) => {
  const ref = useRef<THREE.Group>(null)
  const dir = side === 'west' ? -1 : 1
  const wallX = side === 'west' ? 0 : BUILDING.w
  const docked = wallX + dir * 6.2
  const away = wallX + dir * 34
  const present = num(dock, 'truck_present') > 0

  useFrame((_, delta) => {
    const g = ref.current
    if (!g) return
    const target = present ? docked : away
    if (!g.userData.placed) {
      g.position.x = target
      g.userData.placed = true
    }
    g.position.x += (target - g.position.x) * (1 - Math.exp(-1.5 * delta))
    g.visible = Math.abs(g.position.x - away) > 0.5
  })

  // modelled with the trailer doors at +x; flipped for the east dock
  return (
    <group ref={ref} position={[away, 0, DOCK_Z]} rotation={[0, side === 'west' ? 0 : Math.PI, 0]}>
      <mesh position={[1.2, 2.2, 0]} castShadow>
        <boxGeometry args={[9, 3, 2.6]} />
        <meshStandardMaterial color="#ffffff" roughness={0.6} />
      </mesh>
      <mesh position={[1.2, 1.3, 1.31]}>
        <boxGeometry args={[9, 0.5, 0.02]} />
        <meshStandardMaterial color={color} />
      </mesh>
      <mesh position={[-4.6, 1.6, 0]} castShadow>
        <boxGeometry args={[2.2, 2.4, 2.5]} />
        <meshStandardMaterial color={color} roughness={0.5} />
      </mesh>
      <mesh position={[-5.72, 2.1, 0]}>
        <boxGeometry args={[0.02, 0.9, 2.1]} />
        <meshStandardMaterial color="#1f2a52" />
      </mesh>
      {[-4.6, 2.6, 4.4].map((x) =>
        [-1.15, 1.15].map((z) => (
          <mesh key={`${x}${z}`} position={[x, 0.5, z]} rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.5, 0.5, 0.35, 14]} />
            <meshStandardMaterial color="#2b2f45" />
          </mesh>
        )),
      )}
    </group>
  )
}

/** Trucks at both docks and the pallets staged for shipping. */
export const Logistics3D: React.FC<{ assets: Record<string, LiveAssetTwin> }> = ({ assets }) => {
  const staged = Math.min(12, num(assets['DOCK-SHP'], 'pallets_pending'))
  return (
    <group>
      <Truck dock={assets['DOCK-RCV']} side="west" color={P.trim} />
      <Truck dock={assets['DOCK-SHP']} side="east" color="#12b886" />
      {Array.from({ length: staged }, (_, i) => (
        <mesh key={i} position={[49 - Math.floor(i / 3) * 1.4, 0.5, DOCK_Z - 1.4 + (i % 3) * 1.4]} castShadow>
          <boxGeometry args={[1.1, 1, 1.1]} />
          <meshStandardMaterial color={P.box} roughness={0.9} />
        </mesh>
      ))}
    </group>
  )
}

const Card: React.FC<{ icon: React.ReactNode; title: string; value: string; sub: string }> = ({
  icon, title, value, sub,
}) => (
  <div className="flex items-center gap-2.5 rounded-xl bg-white/95 border border-indigo-100 shadow-md px-3 py-2 min-w-[190px]">
    <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">{icon}</div>
    <div className="leading-tight">
      <div className="text-[10px] uppercase tracking-wide text-slate-500 font-semibold">{title}</div>
      <div className="text-sm font-bold text-slate-900">{value}</div>
      <div className="text-[11px] text-slate-500">{sub}</div>
    </div>
  </div>
)

/** Stat cards over the scene: docks and forklifts at a glance. */
export const LogisticsHud: React.FC<{ assets: Record<string, LiveAssetTwin> }> = ({ assets }) => {
  const rcv = assets['DOCK-RCV']
  const shp = assets['DOCK-SHP']
  if (!rcv || !shp) return null
  const forklifts = Object.values(assets).filter((a) => a.type_id === 'forklift')
  const truck = (d: LiveAssetTwin) =>
    num(d, 'truck_present') > 0 ? `Truck docked · ${Math.round(num(d, 'truck_dwell_s'))} s` : 'No truck'
  return (
    <div className="absolute top-16 left-4 z-10 flex flex-col gap-2" data-testid="logistics-hud">
      <Card
        icon={<TruckIcon className="w-4 h-4" />}
        title="Receiving"
        value={truck(rcv)}
        sub={`${num(rcv, 'pallets_pending')} to unload · ${num(rcv, 'pallets_handled')} received`}
      />
      <Card
        icon={<PackageCheck className="w-4 h-4" />}
        title="Shipping"
        value={truck(shp)}
        sub={`${num(shp, 'pallets_pending')} staged · ${num(shp, 'pallets_handled')} shipped`}
      />
      {forklifts.map((f) => (
        <Card
          key={f.asset_id}
          icon={<Forklift className="w-4 h-4" />}
          title={f.asset_id}
          value={num(f, 'load_kg') > 0 ? 'Carrying pallet' : num(f, 'speed_m_s') > 0 ? 'Driving' : 'Waiting'}
          sub={`Battery ${Math.round(num(f, 'battery_pct'))}% · ${num(f, 'pallets_moved')} moved`}
        />
      ))}
    </div>
  )
}
