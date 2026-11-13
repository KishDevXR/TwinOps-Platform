import React, { useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import type { LiveAssetTwin, StatusColor, VisualizationLayer } from '../../types/twin'

interface MachineMeshProps {
  asset: LiveAssetTwin
  activeLayer: VisualizationLayer
  isSelected: boolean
  isHovered: boolean
  onPointerOver: (e: any) => void
  onPointerOut: (e: any) => void
  onClick: (e: any) => void
}

const STATUS_COLOR_HEX: Record<StatusColor, string> = {
  green: '#22c55e',
  amber: '#f59e0b',
  red: '#ef4444',
  grey: '#64748b',
}

export function getLayerColor(asset: LiveAssetTwin, layer: VisualizationLayer): string {
  if (layer === 'status') {
    return STATUS_COLOR_HEX[asset.status_color] || '#64748b'
  }

  if (layer === 'energy') {
    // Heatmap based on power_kw (0 - 150 kW)
    const power = asset.metrics?.power_kw?.v || asset.metrics?.motor_power_kw?.v || 0
    if (power > 100) return '#ef4444' // red/high
    if (power > 30) return '#f97316'  // orange
    if (power > 10) return '#eab308'  // yellow
    if (power > 1) return '#06b6d4'   // cyan
    return '#3b82f6'                  // blue/low
  }

  if (layer === 'anomaly') {
    // Anomaly score (0.0 to 1.0)
    const score = asset.anomaly_score ?? 0.05
    if (score > 0.8) return '#dc2626' // severe anomaly
    if (score > 0.5) return '#f59e0b' // warning
    if (score > 0.2) return '#38bdf8' // slight deviation
    return '#10b981'                  // normal health
  }

  return STATUS_COLOR_HEX[asset.status_color] || '#64748b'
}

export const MachineMesh: React.FC<MachineMeshProps> = ({
  asset,
  activeLayer,
  isSelected,
  isHovered,
  onPointerOver,
  onPointerOut,
  onClick,
}) => {
  const groupRef = useRef<THREE.Group>(null)
  const beaconRef = useRef<THREE.Mesh>(null)

  const colorHex = getLayerColor(asset, activeLayer)
  const rotYRad = ((asset.position.rot_y || asset.position.rotY || 0) * Math.PI) / 180

  useFrame(({ clock }) => {
    // Pulse beacon light if in alarm or selected
    if (beaconRef.current && (asset.status_color === 'red' || isSelected)) {
      const pulse = (Math.sin(clock.getElapsedTime() * 6) + 1) / 2
      const mat = beaconRef.current.material as THREE.MeshStandardMaterial
      if (mat) {
        mat.emissiveIntensity = 0.5 + pulse * 1.5
      }
    }
  })

  const renderGeometryByType = () => {
    switch (asset.type_id) {
      case 'cnc_machine':
        return (
          <group>
            {/* Main base cabinet */}
            <mesh position={[0, 1.25, 0]} castShadow receiveShadow>
              <boxGeometry args={[2.4, 2.5, 2.0]} />
              <meshStandardMaterial
                color={isSelected ? '#38bdf8' : '#1e293b'}
                roughness={0.4}
                metalness={0.6}
              />
            </mesh>
            {/* Operator door & viewport */}
            <mesh position={[0, 1.4, 1.01]}>
              <boxGeometry args={[1.4, 1.2, 0.05]} />
              <meshStandardMaterial
                color={colorHex}
                roughness={0.2}
                metalness={0.8}
                emissive={colorHex}
                emissiveIntensity={0.2}
              />
            </mesh>
            {/* CNC Spindle Head inside */}
            <mesh position={[0, 1.8, 0.2]}>
              <cylinderGeometry args={[0.2, 0.25, 0.6, 16]} />
              <meshStandardMaterial color="#94a3b8" metalness={0.8} />
            </mesh>
            {/* Control Console */}
            <mesh position={[1.4, 1.3, 0.6]} rotation={[0, -0.3, 0]}>
              <boxGeometry args={[0.4, 0.6, 0.15]} />
              <meshStandardMaterial color="#334155" />
            </mesh>
          </group>
        )

      case 'centrifugal_pump':
        return (
          <group>
            {/* Baseplate */}
            <mesh position={[0, 0.1, 0]} castShadow>
              <boxGeometry args={[1.8, 0.2, 1.0]} />
              <meshStandardMaterial color="#334155" />
            </mesh>
            {/* Electric Motor (Cylindrical) */}
            <mesh position={[-0.4, 0.6, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
              <cylinderGeometry args={[0.35, 0.35, 0.8, 16]} />
              <meshStandardMaterial color="#475569" metalness={0.7} />
            </mesh>
            {/* Pump Volute Casing */}
            <mesh position={[0.45, 0.6, 0]} rotation={[Math.PI / 2, 0, 0]} castShadow>
              <cylinderGeometry args={[0.4, 0.4, 0.35, 16]} />
              <meshStandardMaterial
                color={colorHex}
                emissive={colorHex}
                emissiveIntensity={0.25}
                roughness={0.3}
              />
            </mesh>
            {/* Discharge Flange Pipe */}
            <mesh position={[0.45, 1.0, 0]}>
              <cylinderGeometry args={[0.15, 0.15, 0.5, 16]} />
              <meshStandardMaterial color="#94a3b8" metalness={0.6} />
            </mesh>
          </group>
        )

      case 'robot_cell':
        return (
          <group>
            {/* Pedestal Base */}
            <mesh position={[0, 0.4, 0]} castShadow>
              <cylinderGeometry args={[0.6, 0.7, 0.8, 16]} />
              <meshStandardMaterial color="#1e293b" />
            </mesh>
            {/* Articulated Lower Arm */}
            <mesh position={[0, 1.2, 0]} rotation={[0.2, 0, 0.1]}>
              <boxGeometry args={[0.3, 1.2, 0.3]} />
              <meshStandardMaterial color={colorHex} roughness={0.3} metalness={0.7} />
            </mesh>
            {/* Forearm & End Effector */}
            <mesh position={[0.2, 2.0, 0.3]} rotation={[-0.4, 0, 0]}>
              <boxGeometry args={[0.25, 1.0, 0.25]} />
              <meshStandardMaterial color="#f8fafc" metalness={0.5} />
            </mesh>
            {/* Safety Perimeter Frame */}
            <mesh position={[0, 1.0, 0]}>
              <boxGeometry args={[2.8, 2.0, 2.8]} />
              <meshBasicMaterial color="#38bdf8" wireframe transparent opacity={0.15} />
            </mesh>
          </group>
        )

      case 'conveyor':
        return (
          <group>
            {/* Conveyor Bed */}
            <mesh position={[0, 0.6, 0]} castShadow>
              <boxGeometry args={[3.2, 0.25, 0.9]} />
              <meshStandardMaterial color="#334155" roughness={0.6} />
            </mesh>
            {/* Moving Belt Surface */}
            <mesh position={[0, 0.74, 0]}>
              <boxGeometry args={[3.0, 0.05, 0.8]} />
              <meshStandardMaterial color={colorHex} roughness={0.8} />
            </mesh>
            {/* Legs */}
            <mesh position={[-1.2, 0.3, 0]}>
              <cylinderGeometry args={[0.06, 0.06, 0.6]} />
              <meshStandardMaterial color="#64748b" />
            </mesh>
            <mesh position={[1.2, 0.3, 0]}>
              <cylinderGeometry args={[0.06, 0.06, 0.6]} />
              <meshStandardMaterial color="#64748b" />
            </mesh>
          </group>
        )

      case 'air_compressor':
        return (
          <group>
            {/* Compressor Cabinet */}
            <mesh position={[0, 1.1, 0]} castShadow>
              <boxGeometry args={[2.0, 2.2, 1.4]} />
              <meshStandardMaterial
                color={isSelected ? '#38bdf8' : '#1e293b'}
                metalness={0.5}
              />
            </mesh>
            {/* Top Louver Section */}
            <mesh position={[0, 1.6, 0.71]}>
              <boxGeometry args={[1.6, 0.6, 0.04]} />
              <meshStandardMaterial
                color={colorHex}
                emissive={colorHex}
                emissiveIntensity={0.2}
              />
            </mesh>
            {/* Air Receiver Tank Behind */}
            <mesh position={[0, 1.0, -1.0]} rotation={[0, 0, Math.PI / 2]} castShadow>
              <cylinderGeometry args={[0.45, 0.45, 1.8, 16]} />
              <meshStandardMaterial color="#0284c7" metalness={0.7} />
            </mesh>
          </group>
        )

      case 'chiller':
        return (
          <group>
            {/* Main Chiller Enclosure */}
            <mesh position={[0, 1.25, 0]} castShadow>
              <boxGeometry args={[3.0, 2.5, 1.8]} />
              <meshStandardMaterial color="#0f172a" metalness={0.6} />
            </mesh>
            {/* Top Condenser Fans */}
            <mesh position={[-0.8, 2.55, 0]}>
              <cylinderGeometry args={[0.5, 0.5, 0.15, 16]} />
              <meshStandardMaterial color="#475569" />
            </mesh>
            <mesh position={[0.8, 2.55, 0]}>
              <cylinderGeometry args={[0.5, 0.5, 0.15, 16]} />
              <meshStandardMaterial color="#475569" />
            </mesh>
            {/* Color Accent Grille */}
            <mesh position={[0, 1.2, 0.91]}>
              <boxGeometry args={[2.6, 1.8, 0.05]} />
              <meshStandardMaterial
                color={colorHex}
                emissive={colorHex}
                emissiveIntensity={0.25}
              />
            </mesh>
          </group>
        )

      case 'ahu':
        return (
          <group>
            {/* Suspended Duct Body */}
            <mesh position={[0, 0, 0]} castShadow>
              <boxGeometry args={[3.2, 1.6, 1.6]} />
              <meshStandardMaterial color="#334155" metalness={0.5} />
            </mesh>
            {/* Air Filter Access Panels */}
            <mesh position={[0, 0, 0.81]}>
              <boxGeometry args={[2.6, 1.2, 0.04]} />
              <meshStandardMaterial
                color={colorHex}
                emissive={colorHex}
                emissiveIntensity={0.2}
              />
            </mesh>
          </group>
        )

      case 'energy_meter':
        return (
          <group>
            {/* Electrical Distribution Panel */}
            <mesh position={[0, 0.8, 0]} castShadow>
              <boxGeometry args={[0.8, 1.6, 0.4]} />
              <meshStandardMaterial color="#1e293b" metalness={0.4} />
            </mesh>
            {/* Digital Display Screen */}
            <mesh position={[0, 1.1, 0.21]}>
              <boxGeometry args={[0.5, 0.35, 0.02]} />
              <meshStandardMaterial
                color={colorHex}
                emissive={colorHex}
                emissiveIntensity={0.4}
              />
            </mesh>
          </group>
        )

      default:
        return (
          <mesh position={[0, 1, 0]} castShadow>
            <boxGeometry args={[1.5, 2, 1.5]} />
            <meshStandardMaterial color={colorHex} />
          </mesh>
        )
    }
  }

  return (
    <group
      ref={groupRef}
      position={[asset.position.x, asset.position.y, asset.position.z]}
      rotation={[0, rotYRad, 0]}
      onPointerOver={onPointerOver}
      onPointerOut={onPointerOut}
      onClick={onClick}
    >
      {/* Dynamic Mesh */}
      {renderGeometryByType()}

      {/* Status Warning Beacon (Sphere on top) */}
      <mesh
        ref={beaconRef}
        position={[0, asset.type_id === 'ahu' ? 1.0 : 2.7, 0]}
      >
        <sphereGeometry args={[0.18, 16, 16]} />
        <meshStandardMaterial
          color={colorHex}
          emissive={colorHex}
          emissiveIntensity={asset.status_color === 'red' ? 1.5 : 0.6}
        />
      </mesh>

      {/* Selection Glow Ring on Floor */}
      {isSelected && (
        <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[1.6, 1.85, 32]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} transparent opacity={0.8} />
        </mesh>
      )}

      {/* Hover Bounding Highlight */}
      {isHovered && !isSelected && (
        <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[1.5, 1.7, 32]} />
          <meshBasicMaterial color="#94a3b8" side={THREE.DoubleSide} transparent opacity={0.5} />
        </mesh>
      )}
    </group>
  )
}
