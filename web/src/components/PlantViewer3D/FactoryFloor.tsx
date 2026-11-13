import React from 'react'
import { Text } from '@react-three/drei'
import { AISLE_Z, BUILDING, CHARGER, DOCK_Z, PALETTE as P, RACKS, ZONES } from '../../constants/plantLayout'

const { w: W, d: D } = BUILDING
const FLAT: [number, number, number] = [-Math.PI / 2, 0, 0]

/** Flat rectangle lying on the floor. */
const Slab: React.FC<{ x: number; z: number; w: number; d: number; y?: number; color: string; opacity?: number }> = ({
  x, z, w, d, y = 0.01, color, opacity = 1,
}) => (
  <mesh position={[x, y, z]} rotation={FLAT} receiveShadow>
    <planeGeometry args={[w, d]} />
    <meshStandardMaterial color={color} transparent={opacity < 1} opacity={opacity} roughness={0.9} />
  </mesh>
)

const Wall: React.FC<{ x: number; z: number; w: number; d: number; h: number }> = ({ x, z, w, d, h }) => (
  <group position={[x, 0, z]}>
    <mesh position={[0, h / 2, 0]} castShadow receiveShadow>
      <boxGeometry args={[w, h, d]} />
      <meshStandardMaterial color={P.wall} roughness={0.7} />
    </mesh>
    {/* blue cap trim */}
    <mesh position={[0, h + 0.1, 0]}>
      <boxGeometry args={[w + 0.1, 0.2, d + 0.1]} />
      <meshStandardMaterial color={P.trim} />
    </mesh>
  </group>
)

/** Pallet rack: blue uprights, orange beams, cardboard loads. */
const Rack: React.FC<{ x: number; z: number; bays: number }> = ({ x, z, bays }) => {
  const len = bays * 2
  return (
    <group position={[x, 0, z]}>
      {Array.from({ length: bays + 1 }, (_, i) => (
        <mesh key={i} position={[-len / 2 + i * 2, 2, 0]} castShadow>
          <boxGeometry args={[0.12, 4, 1.1]} />
          <meshStandardMaterial color={P.trim} />
        </mesh>
      ))}
      {[0.2, 1.6, 3].map((y) => (
        <mesh key={y} position={[0, y, 0]}>
          <boxGeometry args={[len, 0.1, 1.1]} />
          <meshStandardMaterial color={P.beam} />
        </mesh>
      ))}
      {Array.from({ length: bays * 3 }, (_, i) => {
        const bay = i % bays
        const level = Math.floor(i / bays)
        if ((bay + level * 2) % 5 === 4) return null // a few empty slots
        return (
          <mesh key={i} position={[-len / 2 + 1 + bay * 2, 0.75 + level * 1.4, 0]} castShadow>
            <boxGeometry args={[1.5, 1, 0.9]} />
            <meshStandardMaterial color={(bay + level) % 3 ? P.box : '#8aa4f0'} roughness={0.9} />
          </mesh>
        )
      })}
    </group>
  )
}

const Tree: React.FC<{ x: number; z: number }> = ({ x, z }) => (
  <group position={[x, 0, z]}>
    <mesh position={[0, 0.8, 0]}>
      <cylinderGeometry args={[0.12, 0.16, 1.6, 8]} />
      <meshStandardMaterial color="#8a6a4f" />
    </mesh>
    <mesh position={[0, 2.3, 0]} castShadow>
      <sphereGeometry args={[1.1, 12, 10]} />
      <meshStandardMaterial color={P.tree} roughness={0.8} />
    </mesh>
  </group>
)

/** Side wall with a dock-door opening at DOCK_Z, plus the door frame. */
const DockWall: React.FC<{ x: number }> = ({ x }) => (
  <group>
    <Wall x={x} z={(DOCK_Z - 2.5) / 2} w={0.4} d={DOCK_Z - 2.5} h={3.2} />
    <Wall x={x} z={(D + DOCK_Z + 2.5) / 2} w={0.4} d={D - DOCK_Z - 2.5} h={3.2} />
    <mesh position={[x, 4.2, DOCK_Z]} castShadow>
      <boxGeometry args={[0.8, 0.8, 6]} />
      <meshStandardMaterial color={P.trim} />
    </mesh>
    {[-2.8, 2.8].map((dz) => (
      <mesh key={dz} position={[x, 2.1, DOCK_Z + dz]} castShadow>
        <boxGeometry args={[0.8, 4.2, 0.5]} />
        <meshStandardMaterial color={P.trim} />
      </mesh>
    ))}
  </group>
)

export const FactoryFloor: React.FC = () => (
  <group>
    {/* Site: ground, truck aprons, perimeter roads */}
    <Slab x={W / 2} z={D / 2} w={220} d={160} y={-0.05} color={P.ground} />
    <Slab x={-9} z={DOCK_Z} w={18} d={14} y={-0.02} color={P.apron} />
    <Slab x={W + 9} z={DOCK_Z} w={18} d={14} y={-0.02} color={P.apron} />
    {[-22, W + 22].map((x) => (
      <group key={x}>
        <Slab x={x} z={D / 2} w={8} d={160} y={-0.03} color={P.road} />
        {Array.from({ length: 20 }, (_, i) => (
          <Slab key={i} x={x} z={-58 + i * 8} w={0.25} d={3} y={-0.01} color="#ffffff" />
        ))}
      </group>
    ))}
    {/* Dock bay markings on the aprons */}
    {[-9, W + 9].map((x) =>
      [-2.2, 2.2].map((dz) => <Slab key={`${x}${dz}`} x={x} z={DOCK_Z + dz} w={16} d={0.15} color={P.line} />),
    )}

    {/* Building shell: tall back wall, dock walls at the sides, open front (cutaway) */}
    <Slab x={W / 2} z={D / 2} w={W} d={D} y={0} color={P.floor} />
    <Wall x={W / 2} z={0} w={W + 0.4} d={0.4} h={6} />
    <DockWall x={0} />
    <DockWall x={W} />
    <Wall x={W / 2} z={D} w={W + 0.4} d={0.4} h={0.25} />

    {/* Zones */}
    {ZONES.map((zn) => (
      <group key={zn.label}>
        <Slab x={zn.x} z={zn.z} w={zn.w} d={zn.d} color={zn.color} opacity={0.75} />
        <Text
          position={[zn.x, 0.03, zn.z + zn.d / 2 - 0.6]}
          rotation={FLAT}
          fontSize={0.7}
          color={P.ink}
          anchorX="center"
          anchorY="middle"
        >
          {zn.label}
        </Text>
      </group>
    ))}

    {/* Forklift aisle: yellow edge lines and dashes */}
    {[-2, 2].map((dz) => (
      <Slab key={dz} x={W / 2} z={AISLE_Z + dz} w={W - 6} d={0.15} y={0.02} color={P.line} />
    ))}
    {Array.from({ length: 12 }, (_, i) => (
      <Slab key={i} x={6 + i * 4} z={AISLE_Z} w={1.6} d={0.12} y={0.02} color="#c5cae6" />
    ))}

    {RACKS.map(([x, z, bays]) => (
      <Rack key={`${x}-${z}`} x={x} z={z} bays={bays} />
    ))}

    {/* Forklift charger */}
    <group position={[CHARGER.x - 1.6, 0, CHARGER.z]}>
      <mesh position={[0, 0.8, 0]} castShadow>
        <boxGeometry args={[0.6, 1.6, 1]} />
        <meshStandardMaterial color={P.wall} />
      </mesh>
      <mesh position={[0.31, 1.1, 0]}>
        <boxGeometry args={[0.02, 0.5, 0.5]} />
        <meshStandardMaterial color={P.tree} emissive={P.tree} emissiveIntensity={0.5} />
      </mesh>
    </group>

    {[[-14, -6], [-14, 26], [-30, 10], [W + 14, -6], [W + 14, 26], [W + 30, 12], [10, -8], [30, -8], [46, -8]].map(
      ([x, z]) => <Tree key={`${x}${z}`} x={x} z={z} />,
    )}
  </group>
)
