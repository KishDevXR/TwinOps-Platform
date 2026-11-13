import { useCallback, useEffect, useState } from 'react'

/** GET a JSON endpoint now and every `everyMs`. `data` stays null until the first success;
 *  after that a failed refresh keeps the last good value. `reload` refetches immediately. */
export function usePoll<T>(url: string | null, everyMs = 15000): { data: T | null; reload: () => void } {
  const [data, setData] = useState<T | null>(null)
  const [tick, setTick] = useState(0)
  const reload = useCallback(() => setTick((t) => t + 1), [])

  useEffect(() => {
    if (!url) return
    let alive = true
    const load = async () => {
      try {
        const res = await fetch(url)
        if (res.ok && alive) setData(await res.json())
      } catch {
        // service down: keep the last good value
      }
    }
    load()
    const t = setInterval(load, everyMs)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [url, everyMs, tick])

  return { data, reload }
}
