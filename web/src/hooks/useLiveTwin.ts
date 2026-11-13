import { useEffect, useRef, useState, useCallback } from 'react'
import type { LiveAssetTwin, AssetPosition, StatusColor } from '../types/twin'
import { PILOT_ASSETS_INITIAL } from '../constants/pilotAssets'

/** A twin as the twin service sends it (REST snapshot, WS snapshot or WS twin_update). */
export interface BackendTwin {
  asset_id: string
  name?: string
  type_id?: string
  criticality?: string
  line_id?: string
  operational_status?: string
  status?: string
  status_color?: StatusColor
  position_3d?: AssetPosition
  position?: AssetPosition
  metrics?: Record<string, { v: number; q: number; unit?: string }>
  derived_metrics?: Record<string, number>
  derived?: Record<string, number>
  last_updated?: string
  last_seen?: string
  ts?: string
  is_stale?: boolean
  anomaly_score?: number
  status_reasons?: string[]
}

/** Map the twin service's field names onto the viewer's, keeping what the update omits. */
export function mergeTwin(existing: LiveAssetTwin | undefined, item: BackendTwin): LiveAssetTwin {
  const metrics = { ...(existing?.metrics ?? {}) }
  for (const [k, m] of Object.entries(item.metrics ?? {})) {
    metrics[k] = { ...metrics[k], ...m } // keep the unit, which updates do not carry
  }
  const statusColor = item.status_color ?? existing?.status_color ?? 'grey'
  return {
    asset_id: item.asset_id,
    name: item.name ?? existing?.name ?? item.asset_id,
    type_id: item.type_id ?? existing?.type_id ?? 'unknown',
    line_id: item.line_id ?? existing?.line_id ?? '',
    criticality: item.criticality ?? existing?.criticality ?? 'C',
    status: item.operational_status ?? item.status ?? existing?.status ?? 'OFFLINE',
    status_color: statusColor,
    position: item.position_3d ?? item.position ?? existing?.position ?? { x: 0, y: 0, z: 0 },
    metrics,
    derived: { ...(existing?.derived ?? {}), ...(item.derived_metrics ?? item.derived ?? {}) },
    last_seen: item.last_updated ?? item.last_seen ?? existing?.last_seen ?? '',
    is_stale: item.is_stale ?? (item.status_color ? statusColor === 'grey' : existing?.is_stale ?? false),
    anomaly_score: item.anomaly_score ?? existing?.anomaly_score,
    status_reasons: item.status_reasons ?? existing?.status_reasons,
  }
}

function mergeAll(prev: Record<string, LiveAssetTwin>, items: BackendTwin[]) {
  const next = { ...prev }
  for (const item of items) next[item.asset_id] = mergeTwin(prev[item.asset_id], item)
  return next
}

interface UseLiveTwinOptions {
  siteId?: string
  wsUrl?: string
  enabled?: boolean
}

interface UseLiveTwinReturn {
  assets: Record<string, LiveAssetTwin>
  selectedAsset: LiveAssetTwin | null
  setSelectedAssetId: (id: string | null) => void
  connectionState: 'connected' | 'connecting' | 'disconnected'
  lastLatencyMs: number
  updateAssetOverride: (assetId: string, partial: Partial<LiveAssetTwin>) => void
  refetchSnapshot: () => Promise<void>
}

export function useLiveTwin({
  siteId = 'PUNE-01',
  wsUrl,
  enabled = true,
}: UseLiveTwinOptions = {}): UseLiveTwinReturn {
  const [assets, setAssets] = useState<Record<string, LiveAssetTwin>>(PILOT_ASSETS_INITIAL)
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null)
  const [connectionState, setConnectionState] = useState<'connected' | 'connecting' | 'disconnected'>('disconnected')
  const [lastLatencyMs, setLastLatencyMs] = useState<number>(14)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<any>(null)

  const fetchRestSnapshot = useCallback(async () => {
    try {
      const res = await fetch(`/api/v1/sites/${siteId}/twin`)
      if (res.ok) {
        const data = await res.json()
        const items: BackendTwin[] | undefined = Array.isArray(data) ? data : data?.assets
        if (items) setAssets((prev) => mergeAll(prev, items))
      }
    } catch {
      // In offline or standalone test mode, keep using initial state
    }
  }, [siteId])

  useEffect(() => {
    if (!enabled) return

    fetchRestSnapshot()

    const resolvedWsUrl =
      wsUrl ||
      `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/live?site=${siteId}`

    function connect() {
      try {
        setConnectionState('connecting')
        const ws = new WebSocket(resolvedWsUrl)
        wsRef.current = ws

        ws.onopen = () => {
          setConnectionState('connected')
        }

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data)
            const recvTime = Date.now()

            // twin service sends {type:'snapshot', assets:[...]} and flat twin_update objects
            const snapshot: BackendTwin[] | undefined = msg.assets ?? msg.data
            if (msg.type === 'snapshot' && snapshot) {
              setAssets((prev) => mergeAll(prev, snapshot))
            } else if (msg.type === 'twin_update') {
              const item: BackendTwin = msg.data ?? msg
              const stamp = item.last_updated ?? item.ts
              if (stamp) {
                const sendTime = new Date(stamp).getTime()
                if (!isNaN(sendTime) && sendTime > 0) {
                  const latency = Math.max(1, recvTime - sendTime)
                  setLastLatencyMs(latency)
                }
              }

              setAssets((prev) => {
                const existing = prev[item.asset_id]
                if (!existing) return prev
                return { ...prev, [item.asset_id]: mergeTwin(existing, item) }
              })
            }
          } catch {
            // ignore non-json
          }
        }

        ws.onerror = () => {
          setConnectionState('disconnected')
        }

        ws.onclose = () => {
          setConnectionState('disconnected')
          reconnectTimeoutRef.current = setTimeout(connect, 3000)
        }
      } catch {
        setConnectionState('disconnected')
        reconnectTimeoutRef.current = setTimeout(connect, 3000)
      }
    }

    connect()

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [enabled, fetchRestSnapshot, siteId, wsUrl])

  const updateAssetOverride = useCallback((assetId: string, partial: Partial<LiveAssetTwin>) => {
    setAssets((prev) => {
      const existing = prev[assetId]
      if (!existing) return prev
      return {
        ...prev,
        [assetId]: {
          ...existing,
          ...partial,
        },
      }
    })
  }, [])

  const selectedAsset = selectedAssetId ? assets[selectedAssetId] || null : null

  return {
    assets,
    selectedAsset,
    setSelectedAssetId,
    connectionState,
    lastLatencyMs,
    updateAssetOverride,
    refetchSnapshot: fetchRestSnapshot,
  }
}
