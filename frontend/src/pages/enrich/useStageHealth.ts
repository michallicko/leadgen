/**
 * useStageHealth — polls GET /api/enrich/stage-health for per-stage
 * failed and needs_review counts.
 */

import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'

interface StageHealthData {
  failed: number
  needs_review: number
}

interface StageHealthResponse {
  stages: Record<string, StageHealthData>
}

export function useStageHealth(batchName: string) {
  return useQuery({
    queryKey: ['stage-health', batchName],
    queryFn: () =>
      apiFetch<StageHealthResponse>('/enrich/stage-health', {
        params: { batch_name: batchName },
      }),
    enabled: !!batchName,
    refetchInterval: 30_000,
  })
}
