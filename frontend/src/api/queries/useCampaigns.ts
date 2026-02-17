import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'

export interface Campaign {
  id: string
  name: string
  status: string
  description: string | null
  owner_name: string | null
  total_contacts: number
  generated_count: number
  generation_cost: number
  template_config: TemplateStep[]
  generation_config: Record<string, unknown>
  created_at: string | null
  updated_at: string | null
}

export interface CampaignDetail extends Campaign {
  owner_id: string | null
  generation_started_at: string | null
  generation_completed_at: string | null
  contact_status_counts: Record<string, number>
}

export interface TemplateStep {
  step: number
  channel: string
  label: string
  enabled: boolean
  needs_pdf: boolean
  variant_count: number
}

export interface CampaignTemplate {
  id: string
  name: string
  description: string | null
  steps: TemplateStep[]
  default_config: Record<string, unknown>
  is_system: boolean
  created_at: string | null
}

interface CampaignsResponse {
  campaigns: Campaign[]
}

interface TemplatesResponse {
  templates: CampaignTemplate[]
}

export function useCampaigns() {
  return useQuery({
    queryKey: ['campaigns'],
    queryFn: () => apiFetch<CampaignsResponse>('/campaigns'),
  })
}

export function useCampaign(id: string | null) {
  return useQuery({
    queryKey: ['campaign', id],
    queryFn: () => apiFetch<CampaignDetail>(`/campaigns/${id}`),
    enabled: !!id,
  })
}

export function useCampaignTemplates() {
  return useQuery({
    queryKey: ['campaign-templates'],
    queryFn: () => apiFetch<TemplatesResponse>('/campaign-templates'),
  })
}

export function useCreateCampaign() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; description?: string; owner_id?: string; template_id?: string }) =>
      apiFetch<{ id: string; name: string; status: string; created_at: string }>('/campaigns', {
        method: 'POST',
        body: data,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaigns'] })
    },
  })
}

export function useUpdateCampaign() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      apiFetch<{ ok: boolean }>(`/campaigns/${id}`, { method: 'PATCH', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaigns'] })
    },
  })
}

export function useDeleteCampaign() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<{ ok: boolean }>(`/campaigns/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaigns'] })
    },
  })
}
