import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'

export interface StepConfig {
  max_length?: number
  tone?: string
  language?: string
  custom_instructions?: string
  example_messages?: ExampleMessage[]
}

export interface ExampleMessage {
  body: string
  note?: string
}

export interface CampaignStep {
  id: string
  campaign_id: string
  position: number
  channel: string
  day_offset: number
  label: string
  config: StepConfig
  created_at: string | null
  updated_at: string | null
}

interface StepsResponse {
  steps: CampaignStep[]
}

export function useCampaignSteps(campaignId: string | null) {
  return useQuery({
    queryKey: ['campaign-steps', campaignId],
    queryFn: () => apiFetch<StepsResponse>(`/campaigns/${campaignId}/steps`),
    enabled: !!campaignId,
  })
}

export function useAddCampaignStep() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      campaignId,
      data,
    }: {
      campaignId: string
      data: { channel?: string; day_offset?: number; label?: string; config?: StepConfig }
    }) =>
      apiFetch<CampaignStep>(`/campaigns/${campaignId}/steps`, {
        method: 'POST',
        body: data,
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['campaign-steps', vars.campaignId] })
    },
  })
}

export function useUpdateCampaignStep() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      campaignId,
      stepId,
      data,
    }: {
      campaignId: string
      stepId: string
      data: { channel?: string; day_offset?: number; label?: string; config?: StepConfig }
    }) =>
      apiFetch<CampaignStep>(`/campaigns/${campaignId}/steps/${stepId}`, {
        method: 'PATCH',
        body: data,
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['campaign-steps', vars.campaignId] })
    },
  })
}

export function useDeleteCampaignStep() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ campaignId, stepId }: { campaignId: string; stepId: string }) =>
      apiFetch<{ ok: boolean }>(`/campaigns/${campaignId}/steps/${stepId}`, {
        method: 'DELETE',
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['campaign-steps', vars.campaignId] })
    },
  })
}

export function useReorderCampaignSteps() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ campaignId, order }: { campaignId: string; order: string[] }) =>
      apiFetch<StepsResponse>(`/campaigns/${campaignId}/steps/reorder`, {
        method: 'PUT',
        body: { order },
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['campaign-steps', vars.campaignId] })
    },
  })
}

export function usePopulateFromTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ campaignId, templateId }: { campaignId: string; templateId: string }) =>
      apiFetch<StepsResponse>(`/campaigns/${campaignId}/steps/from-template`, {
        method: 'POST',
        body: { template_id: templateId },
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['campaign-steps', vars.campaignId] })
    },
  })
}
