/**
 * useEnrichEstimate — React Query hook that POSTs to /api/enrich/estimate
 * whenever filters or enabled stages change.
 */

import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'
import type { EnrichFilters, StageEstimate } from './StageCard.types'

interface EstimateResponse {
  stages: Record<string, StageEstimate>
  total_estimated_cost: number
}

export function useEnrichEstimate(
  filters: EnrichFilters,
  enabledStages: string[],
  softDepsPayload: Record<string, boolean>,
  reEnrichPayload?: Record<string, { enabled: boolean; horizon: string | null }>,
) {
  return useQuery({
    queryKey: ['enrich-estimate', filters.tag, filters.owner, filters.tier, filters.status, filters.entityIds, filters.limit, enabledStages, reEnrichPayload],
    queryFn: () => {
      const body: Record<string, unknown> = {
        tag_name: filters.tag,
        stages: enabledStages,
        soft_deps: softDepsPayload,
      }
      if (filters.owner) body.owner_name = filters.owner
      if (filters.tier) body.tier_filter = [filters.tier]
      if (filters.status) body.status_filter = filters.status
      if (filters.limit) body.limit = Number(filters.limit)
      if (filters.entityIds) {
        body.entity_ids = filters.entityIds.split(',').map((s) => s.trim()).filter(Boolean)
      }
      if (reEnrichPayload) {
        body.re_enrich = reEnrichPayload
      }

      return apiFetch<EstimateResponse>('/enrich/estimate', {
        method: 'POST',
        body,
      })
    },
    enabled: !!filters.tag && enabledStages.length > 0,
    staleTime: 10_000,
  })
}
