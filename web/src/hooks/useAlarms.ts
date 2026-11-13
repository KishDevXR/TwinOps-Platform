import { useCallback } from 'react'
import type { AlarmItem } from '../types/twin'
import { usePoll } from './usePoll'

/** Active alarms from the alarm service (port 8004), with acknowledge. */
export function useAlarms(everyMs = 5000) {
  const { data, reload } = usePoll<{ alarms: AlarmItem[] }>('/api/v1/alarms?state=active', everyMs)

  const acknowledge = useCallback(
    async (id: string | number) => {
      try {
        await fetch(`/api/v1/alarms/${id}/ack`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          // shortcut: no login yet, so acks are recorded against a fixed operator id
          body: JSON.stringify({ user_id: 'web-operator' }),
        })
      } finally {
        reload()
      }
    },
    [reload],
  )

  return { alarms: data?.alarms ?? [], loaded: data !== null, acknowledge }
}
