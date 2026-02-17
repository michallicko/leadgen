/**
 * useRunHistory — React Query hooks for pipeline run history and per-entity results.
 */

import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'
import type { EntityResult } from '../../components/ui/EntityResultsTable'

interface PipelineRun {
  id: string
  status: string
  cost: number
  stages: string[]
  config: Record<string, unknown>
  started_at: string | null
  completed_at: string | null
  duration_s: number | null
}

interface RunsResponse {
  runs: PipelineRun[]
  total: number
}

interface EntitiesResponse {
  entities: EntityResult[]
  total: number
}

export function useRunHistory(batchName: string, page = 1) {
  return useQuery({
    queryKey: ['pipeline-runs', batchName, page],
    queryFn: () =>
      apiFetch<RunsResponse>('/pipeline/runs', {
        params: { batch_name: batchName, page: String(page), per_page: '10' },
      }),
    enabled: !!batchName,
  })
}

export function useRunEntities(
  runId: string | null,
  stage?: string,
  status?: string,
  page = 1,
) {
  return useQuery({
    queryKey: ['pipeline-run-entities', runId, stage, status, page],
    queryFn: () => {
      const params: Record<string, string> = {
        page: String(page),
        per_page: '50',
      }
      if (stage) params.stage = stage
      if (status) params.status = status
      return apiFetch<EntitiesResponse>(`/pipeline/runs/${runId}/entities`, { params })
    },
    enabled: !!runId,
  })
}

export type { PipelineRun }
