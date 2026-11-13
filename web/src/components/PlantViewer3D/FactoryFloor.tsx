import React from 'react'
import * as THREE from 'three'
import { Text } from '@react-three/drei'

export const FactoryFloor: React.FC = () => {
  return (
    <group>
      {/* Main Concrete Floor Plate */}
      <mesh position={[12, -0.01, 15]} receiveShadow>
        <planeGeometry args={[45, 40]} />
        <meshStandardMaterial
          color="#0b1120"
          roughness={0.8}
          metalness={0.2}
        />
      </mesh>

      {/* Grid Helper on Floor */}
      <gridHelper
        args={[45, 45, '#1e293b', '#0f172a']}
        position={[12, 0.01, 15]}
      />

      {/* Safety Walkway Line 1 Bay Boundary (Yellow Stripe) */}
      <mesh position={[12, 0.02, 10]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[35, 0.2]} />
        <meshBasicMaterial color="#eab308" side={THREE.DoubleSide} />
      </mesh>

      {/* Line 2 Bay Boundary (Yellow Stripe) */}
      <mesh position={[12, 0.02, 16]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[35, 0.2]} />
        <meshBasicMaterial color="#eab308" side={THREE.DoubleSide} />
      </mesh>

      {/* Line 1 Walkway / Bay Sign */}
      <Text
        position={[1, 0.03, 5]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={1.2}
        color="#38bdf8"
        anchorX="center"
        anchorY="middle"
      >
        LINE 01 — MACHINING BAY A
      </Text>

      {/* Line 2 Walkway / Bay Sign */}
      <Text
        position={[1, 0.03, 20]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={1.2}
        color="#38bdf8"
        anchorX="center"
        anchorY="middle"
      >
        LINE 02 — MACHINING BAY B
      </Text>

      {/* Utilities Zone Sign */}
      <Text
        position={[12, 0.03, 13.5]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={0.8}
        color="#64748b"
        anchorX="center"
        anchorY="middle"
      >
        CENTRAL UTILITIES CORRIDOR (PUMPS / COMPRESSORS / CHILLERS)
      </Text>
    </group>
  )
}
