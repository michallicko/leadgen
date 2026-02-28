import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'

// ── Types ──────────────────────────────────────────────

export interface GenerationStatusResponse {
  status: string
  total_contacts: number
  generated_count: number
  generation_cost: number
  progress_pct: number
  contact_statuses: Record<string, number>
  channels?: Record<string, { generated: number; target: number }>
  failed_contacts?: Array<{
    contact_id: string
    name: string
    error: string
  }>
}

export interface CostEstimateResponse {
  total_contacts: number
  total_messages: number
  estimated_cost: number
  by_step: Array<{
    step: number
    label: string
    channel: string
    count: number
    cost: number
  }>
  enrichment_gaps?: {
    total_contacts: number
    enriched_contacts: number
    unenriched_contacts: number
    gap_details: Array<{
      contact_id: string
      name: string
      missing_stages: string[]
    }>
  }
}

// ── Hooks ──────────────────────────────────────────────

/**
 * Poll generation status every 2 seconds while generation is active.
 */
export function useGenerationStatus(campaignId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ['generation-status', campaignId],
    queryFn: () =>
      apiFetch<GenerationStatusResponse>(`/campaigns/${campaignId}/generation-status`),
    enabled: enabled && !!campaignId,
    refetchInterval: 2000,
  })
}

/**
 * Start message generation for a campaign.
 */
export function useStartGeneration() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ campaignId, skipUnenriched }: { campaignId: string; skipUnenriched?: boolean }) =>
      apiFetch<{ ok: boolean; status: string }>(`/campaigns/${campaignId}/generate`, {
        method: 'POST',
        body: skipUnenriched ? { skip_unenriched: true } : undefined,
      }),
    onSuccess: (_, { campaignId }) => {
      qc.invalidateQueries({ queryKey: ['campaign', campaignId] })
      qc.invalidateQueries({ queryKey: ['generation-status', campaignId] })
      qc.invalidateQueries({ queryKey: ['campaigns'] })
    },
  })
}

/**
 * Get cost estimate before generation.
 */
export function useCostEstimate() {
  return useMutation({
    mutationFn: (campaignId: string) =>
      apiFetch<CostEstimateResponse>(`/campaigns/${campaignId}/cost-estimate`, {
        method: 'POST',
      }),
  })
}

/**
 * Cancel active generation (sets status back to Ready).
 */
export function useCancelGeneration() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (campaignId: string) =>
      apiFetch<{ ok: boolean }>(`/campaigns/${campaignId}/generate`, {
        method: 'DELETE',
      }),
    onSuccess: (_, campaignId) => {
      qc.invalidateQueries({ queryKey: ['campaign', campaignId] })
      qc.invalidateQueries({ queryKey: ['generation-status', campaignId] })
      qc.invalidateQueries({ queryKey: ['campaigns'] })
    },
  })
}
