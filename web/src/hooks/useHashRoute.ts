import { useEffect, useState } from 'react'

export type Route =
  | { page: 'dashboard' }
  | { page: 'assets'; q: string }
  | { page: 'asset'; id: string }
  | { page: 'plant'; id?: string }
  | { page: 'insights' }
  | { page: 'users' }

/** '#/assets/CNC-01' -> { page: 'asset', id: 'CNC-01' }. Unknown paths go to the dashboard. */
export function parseRoute(hash: string): Route {
  const [path, query = ''] = hash.replace(/^#\/?/, '').split('?')
  const [page, id] = path.split('/').map(decodeURIComponent)
  if (page === 'assets' && id) return { page: 'asset', id }
  if (page === 'assets') return { page: 'assets', q: new URLSearchParams(query).get('q') ?? '' }
  if (page === 'plant') return id ? { page: 'plant', id } : { page: 'plant' }
  if (page === 'insights' || page === 'users') return { page }
  return { page: 'dashboard' }
}

export function routeHref(r: Route): string {
  switch (r.page) {
    case 'asset':
      return `#/assets/${encodeURIComponent(r.id)}`
    case 'assets':
      return r.q ? `#/assets?q=${encodeURIComponent(r.q)}` : '#/assets'
    case 'plant':
      return r.id ? `#/plant/${encodeURIComponent(r.id)}` : '#/plant'
    default:
      return `#/${r.page}`
  }
}

export function navigate(r: Route) {
  window.location.hash = routeHref(r)
}

export function useHashRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash))
  useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash))
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}
