import { useLiveTwin } from './hooks/useLiveTwin'
import { useAlarms } from './hooks/useAlarms'
import { useHashRoute } from './hooks/useHashRoute'
import { useInsights } from './hooks/useInsights'
import { Sidebar, Topbar } from './components/layout/AppShell'
import { DashboardPage } from './pages/DashboardPage'
import { AssetLibraryPage } from './pages/AssetLibraryPage'
import { AssetDetailPage } from './pages/AssetDetailPage'
import { PlantPage } from './pages/PlantPage'
import { InsightsPage } from './pages/InsightsPage'
import { UsersPage } from './pages/UsersPage'

export function App() {
  const route = useHashRoute()
  const { assets, connectionState, lastLatencyMs, updateAssetOverride, refetchSnapshot } = useLiveTwin({ siteId: 'PUNE-01' })
  const { alarms, acknowledge } = useAlarms()
  const { insights, pmPlans, workOrders, parts } = useInsights(assets, alarms)

  let page
  switch (route.page) {
    case 'assets':
      page = <AssetLibraryPage key={route.q} twins={assets} initialQuery={route.q} />
      break
    case 'asset':
      page = <AssetDetailPage key={route.id} id={route.id} twin={assets[route.id]} alarms={alarms} onAcknowledge={acknowledge} pmPlans={pmPlans} />
      break
    case 'plant':
      page = (
        <PlantPage
          assets={assets}
          selectedId={route.id ?? null}
          alarms={alarms}
          onAcknowledge={acknowledge}
          updateAssetOverride={updateAssetOverride}
          refetchSnapshot={refetchSnapshot}
        />
      )
      break
    case 'insights':
      page = <InsightsPage insights={insights} />
      break
    case 'users':
      page = <UsersPage />
      break
    default:
      page = <DashboardPage twins={assets} alarms={alarms} insights={insights} workOrders={workOrders} pmPlans={pmPlans} parts={parts} />
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#eef2f9] text-slate-900">
      <Sidebar active={route.page} />
      <div className="flex-1 min-w-0 flex flex-col">
        <Topbar connectionState={connectionState} lastLatencyMs={lastLatencyMs} alarmCount={alarms.length} onRefresh={refetchSnapshot} />
        {route.page === 'plant' ? (
          <main className="flex-1 min-h-0">{page}</main>
        ) : (
          <main className="flex-1 min-h-0 overflow-y-auto">
            <div className="max-w-[1500px] mx-auto p-6">{page}</div>
          </main>
        )}
      </div>
    </div>
  )
}

export default App
