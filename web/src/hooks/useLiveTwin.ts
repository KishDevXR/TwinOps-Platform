import { useEffect, useRef, useState, useCallback } from 'react'
import type { LiveAssetTwin, AlarmItem } from '../types/twin'
import { PILOT_ASSETS_INITIAL } from '../constants/pilotAssets'

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
  alarms: AlarmItem[]
  acknowledgeAlarm: (id: string | number) => void
  updateAssetOverride: (assetId: string, partial: Partial<LiveAssetTwin>) => void
  refetchSnapshot: () => Promise<void>
}

export function useLiveTwin({
  siteId = 'PUNE-01',
  wsUrl,
  enabled = true,
}: UseLiveTwinOptions = {}): UseLiveTwinReturn {
  const [assets, setAssets] = useState<Record<string, LiveAssetTwin>>(PILOT_ASSETS_INITIAL)
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>('CNC-01')
  const [connectionState, setConnectionState] = useState<'connected' | 'connecting' | 'disconnected'>('disconnected')
  const [lastLatencyMs, setLastLatencyMs] = useState<number>(14)
  const [alarms, setAlarms] = useState<AlarmItem[]>([
    {
      id: 'ALM-101',
      asset_id: 'CNC-02',
      metric: 'spindle_temp_c',
      severity: 'high',
      message: 'CNC-02 spindle temperature elevated (Warning threshold 65°C)',
      value: 68.4,
      raised_at: new Date(Date.now() - 300000).toISOString(),
      state: 'active',
    },
    {
      id: 'ALM-102',
      asset_id: 'COMP-01',
      metric: 'oil_temp_c',
      severity: 'medium',
      message: 'COMP-01 compressor oil temp near upper warning limit',
      value: 78.2,
      raised_at: new Date(Date.now() - 600000).toISOString(),
      state: 'active',
    },
  ])

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<any>(null)

  const fetchRestSnapshot = useCallback(async () => {
    try {
      const res = await fetch(`/api/v1/sites/${siteId}/twin`)
      if (res.ok) {
        const data = await res.json()
        if (data && data.assets) {
          setAssets((prev) => {
            const next = { ...prev }
            for (const item of data.assets) {
              const existing = prev[item.asset_id]
              next[item.asset_id] = {
                ...(existing || {}),
                ...item,
                position: existing?.position || item.position || { x: 0, y: 0, z: 0 },
              }
            }
            return next
          })
        }
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

            if (msg.type === 'snapshot' && msg.data) {
              setAssets((prev) => {
                const next = { ...prev }
                for (const item of msg.data) {
                  const existing = prev[item.asset_id]
                  next[item.asset_id] = {
                    ...(existing || {}),
                    ...item,
                    position: existing?.position || item.position || { x: 0, y: 0, z: 0 },
                  }
                }
                return next
              })
            } else if (msg.type === 'twin_update' && msg.data) {
              const item = msg.data
              if (item.ts) {
                const sendTime = new Date(item.ts).getTime()
                if (!isNaN(sendTime) && sendTime > 0) {
                  const latency = Math.max(1, recvTime - sendTime)
                  setLastLatencyMs(latency)
                }
              }

              setAssets((prev) => {
                const existing = prev[item.asset_id]
                if (!existing) return prev
                return {
                  ...prev,
                  [item.asset_id]: {
                    ...existing,
                    ...item,
                    metrics: { ...existing.metrics, ...(item.metrics || {}) },
                    derived: { ...existing.derived, ...(item.derived || {}) },
                  },
                }
              })

              // Check if status changed to red or fault, add alarm if not present
              if (item.status_color === 'red' || item.status === 'FAULT') {
                setAlarms((prevAlarms) => {
                  const exists = prevAlarms.some((a) => a.asset_id === item.asset_id && a.state === 'active')
                  if (!exists) {
                    return [
                      {
                        id: `ALM-${Date.now()}`,
                        asset_id: item.asset_id,
                        metric: 'status_alarm',
                        severity: 'critical',
                        message: `${item.name || item.asset_id} fault detected: Status Red`,
                        raised_at: new Date().toISOString(),
                        state: 'active',
                      },
                      ...prevAlarms,
                    ]
                  }
                  return prevAlarms
                })
              }
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

  const acknowledgeAlarm = useCallback((id: string | number) => {
    setAlarms((prev) =>
      prev.map((a) => (a.id === id ? { ...a, state: 'acked' } : a))
    )
  }, [])

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
    alarms,
    acknowledgeAlarm,
    updateAssetOverride,
    refetchSnapshot: fetchRestSnapshot,
  }
}
