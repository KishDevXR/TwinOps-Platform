import React, { useMemo } from 'react'
import { Canvas } from '@react-three/fiber'
import { Bounds, OrbitControls, PerspectiveCamera, View } from '@react-three/drei'
import type { LiveAssetTwin } from '../../types/twin'
import { MachineMesh } from './ParametricMeshes'
import { FactoryFloor } from './FactoryFloor'
import { Logistics3D } from './Logistics'
import { PALETTE } from '../../constants/plantLayout'

const noop = () => {}

/** One asset's mesh at the origin, coloured by live status. */
export const AssetModel: React.FC<{ asset: LiveAssetTwin }> = ({ asset }) => {
  const centred = useMemo<LiveAssetTwin>(() => {
    const metrics = { ...asset.metrics }
    // forklifts place themselves from live position metrics; pin them to the origin here
    if (metrics.pos_x_m) metrics.pos_x_m = { ...metrics.pos_x_m, v: 0 }
    if (metrics.pos_z_m) metrics.pos_z_m = { ...metrics.pos_z_m, v: 0 }
    return { ...asset, metrics, position: { x: 0, y: 0, z: 0, rot_y: 0 } }
  }, [asset])
  return (
    <MachineMesh
      asset={centred}
      activeLayer="status"
      isSelected={false}
      isHovered={false}
      onPointerOver={noop}
      onPointerOut={noop}
      onClick={noop}
    />
  )
}

const Lights = () => (
  <>
    <ambientLight intensity={1.4} />
    <hemisphereLight args={['#ffffff', '#c9d0f0', 0.5]} />
    <directionalLight position={[6, 10, 8]} intensity={1.2} />
  </>
)

/** Rotatable single-asset viewer for the asset details page. */
export const AssetPreview3D: React.FC<{ asset: LiveAssetTwin }> = ({ asset }) => (
  <Canvas flat camera={{ position: [6, 4.5, 7], fov: 35 }} dpr={[1, 2]}>
    <color attach="background" args={['#dfe6f5']} />
    <Lights />
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]}>
      <circleGeometry args={[6, 48]} />
      <meshStandardMaterial color="#f8f9fd" />
    </mesh>
    <gridHelper args={[12, 12, '#c7d0e8', '#dfe5f3']} position={[0, 0, 0]} />
    <Bounds fit clip observe margin={1.6}>
      <AssetModel asset={asset} />
    </Bounds>
    <OrbitControls makeDefault autoRotate autoRotateSpeed={0.8} minDistance={2} maxDistance={30} maxPolarAngle={Math.PI / 2.05} />
  </Canvas>
)

/** Thumbnail slot in a card. Draws into the single <ThumbnailCanvas/> on the page, because
 *  browsers allow only ~16 live WebGL contexts and the library shows up to 29 cards. */
export const AssetThumb: React.FC<{ asset: LiveAssetTwin; className?: string }> = ({ asset, className }) => (
  <View className={className}>
    <color attach="background" args={['#e7ecf7']} />
    <PerspectiveCamera makeDefault position={[5, 4, 6]} fov={35} />
    <Lights />
    <Bounds fit clip margin={1.3}>
      <AssetModel asset={asset} />
    </Bounds>
  </View>
)

/** The one canvas behind every <AssetThumb/>. Mount once per page, after the thumbs. */
export const ThumbnailCanvas: React.FC<{ eventSource: React.RefObject<HTMLElement | null> }> = ({ eventSource }) => (
  <Canvas
    flat
    eventSource={eventSource as React.RefObject<HTMLElement>}
    className="!fixed inset-0 pointer-events-none"
    style={{ position: 'fixed', inset: 0, pointerEvents: 'none' }}
  >
    <View.Port />
  </Canvas>
)

/** Small auto-rotating view of the whole plant for the dashboard header. */
export const MiniPlant3D: React.FC<{ assets: Record<string, LiveAssetTwin> }> = ({ assets }) => (
  <Canvas flat camera={{ position: [70, 48, 78], fov: 30, far: 600 }} dpr={[1, 1.5]}>
    <color attach="background" args={[PALETTE.sky]} />
    <ambientLight intensity={1.5} />
    <hemisphereLight args={['#ffffff', '#c9d0f0', 0.5]} />
    <directionalLight position={[50, 70, 60]} intensity={1.1} />
    <FactoryFloor />
    <Logistics3D assets={assets} />
    {Object.values(assets).map((a) => (
      <MachineMesh
        key={a.asset_id}
        asset={a}
        activeLayer="status"
        isSelected={false}
        isHovered={false}
        onPointerOver={noop}
        onPointerOut={noop}
        onClick={noop}
      />
    ))}
    <OrbitControls target={[28, 0, 18]} autoRotate autoRotateSpeed={0.4} enableZoom={false} enablePan={false} maxPolarAngle={Math.PI / 2.4} minPolarAngle={Math.PI / 4} />
  </Canvas>
)
