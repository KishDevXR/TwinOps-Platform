import { useMemo } from 'react'
import type { AlarmItem, LiveAssetTwin } from '../types/twin'
import { buildInsights, type Part, type PmPlan, type WorkOrder } from '../pages/insights'
import { usePoll } from './usePoll'

/** Maintenance data plus the insights derived from it and the live twins. */
export function useInsights(twins: Record<string, LiveAssetTwin>, alarms: AlarmItem[]) {
  const pmPlans = usePoll<PmPlan[]>('/api/v1/pm-plans', 60000).data
  const workOrders = usePoll<{ work_orders: WorkOrder[] }>('/api/v1/work-orders', 10000).data?.work_orders ?? null
  const parts = usePoll<Part[]>('/api/v1/parts', 30000).data
  const insights = useMemo(
    () => buildInsights({ twins, alarms, pmPlans, workOrders, parts }),
    [twins, alarms, pmPlans, workOrders, parts],
  )
  return { insights, pmPlans, workOrders, parts }
}
