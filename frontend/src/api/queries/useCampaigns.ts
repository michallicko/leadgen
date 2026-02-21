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

export interface SenderConfig {
  from_email?: string
  from_name?: string
  reply_to?: string
  linkedin_daily_connections?: number
  linkedin_daily_messages?: number
  linkedin_active_hours?: { start: string; end: string }
  linkedin_delay_range?: { min: number; max: number }
}

export interface CampaignDetail extends Campaign {
  owner_id: string | null
  generation_started_at: string | null
  generation_completed_at: string | null
  sender_config: SenderConfig
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

// ── Campaign Contacts ──────────────────────────────────

export interface CampaignContactItem {
  campaign_contact_id: string
  status: string
  enrichment_gaps: string[]
  generation_cost: number
  error: string | null
  added_at: string | null
  generated_at: string | null
  contact_id: string
  first_name: string | null
  last_name: string | null
  full_name: string
  job_title: string | null
  email_address: string | null
  linkedin_url: string | null
  contact_score: number | null
  icp_fit: string | null
  company_id: string | null
  company_name: string | null
  company_tier: string | null
  company_status: string | null
}

interface CampaignContactsResponse {
  contacts: CampaignContactItem[]
  total: number
}

export function useCampaignContacts(campaignId: string | null) {
  return useQuery({
    queryKey: ['campaign-contacts', campaignId],
    queryFn: () => apiFetch<CampaignContactsResponse>(`/campaigns/${campaignId}/contacts`),
    enabled: !!campaignId,
  })
}

export function useAddCampaignContacts() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ campaignId, contactIds, companyIds }: {
      campaignId: string
      contactIds?: string[]
      companyIds?: string[]
    }) =>
      apiFetch<{ added: number; skipped: number; total: number }>(
        `/campaigns/${campaignId}/contacts`,
        { method: 'POST', body: { contact_ids: contactIds, company_ids: companyIds } },
      ),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['campaign-contacts', vars.campaignId] })
      qc.invalidateQueries({ queryKey: ['campaign', vars.campaignId] })
      qc.invalidateQueries({ queryKey: ['campaigns'] })
    },
  })
}

export function useRemoveCampaignContacts() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ campaignId, contactIds }: { campaignId: string; contactIds: string[] }) =>
      apiFetch<{ removed: number }>(
        `/campaigns/${campaignId}/contacts`,
        { method: 'DELETE', body: { contact_ids: contactIds } },
      ),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['campaign-contacts', vars.campaignId] })
      qc.invalidateQueries({ queryKey: ['campaign', vars.campaignId] })
      qc.invalidateQueries({ queryKey: ['campaigns'] })
    },
  })
}
