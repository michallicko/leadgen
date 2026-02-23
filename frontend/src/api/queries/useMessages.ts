import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'

export interface MessageContact {
  id: string | null
  full_name: string
  first_name: string | null
  last_name: string | null
  job_title: string | null
  linkedin_url: string | null
  contact_score: number | null
  icp_fit: string | null
  owner_name: string | null
  tag_name: string | null
}

export interface MessageCompany {
  id: string | null
  name: string | null
  tier: string | null
  domain: string | null
  status: string | null
}

export interface Message {
  id: string
  channel: string
  sequence_step: number
  variant: string
  subject: string | null
  body: string
  status: string
  tone: string | null
  language: string | null
  generation_cost: number | null
  review_notes: string | null
  approved_at: string | null
  original_body: string | null
  original_subject: string | null
  edit_reason: string | null
  edit_reason_text: string | null
  regen_count: number
  regen_config: Record<string, unknown> | null
  label: string | null
  campaign_contact_id: string | null
  contact: MessageContact
  company: MessageCompany | null
}

export interface MessagesResponse {
  messages: Message[]
}

export interface MessageFilters {
  status?: string
  owner_name?: string
  channel?: string
  campaign_id?: string
}

export function useMessages(filters: MessageFilters) {
  return useQuery({
    queryKey: ['messages', filters],
    queryFn: () => {
      const params: Record<string, string> = {}
      if (filters.status) params.status = filters.status
      if (filters.owner_name) params.owner_name = filters.owner_name
      if (filters.channel) params.channel = filters.channel
      if (filters.campaign_id) params.campaign_id = filters.campaign_id
      return apiFetch<MessagesResponse>('/messages', { params })
    },
    enabled: false, // Manual trigger via refetch
  })
}

export function useUpdateMessage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      apiFetch<{ ok: boolean }>(`/messages/${id}`, { method: 'PATCH', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['messages'] })
    },
  })
}

export function useBatchUpdateMessages() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ ids, fields }: { ids: string[]; fields: Record<string, unknown> }) =>
      apiFetch<{ ok: boolean; updated: number }>('/messages/batch', {
        method: 'PATCH',
        body: { ids, fields },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['messages'] })
    },
  })
}

// ── Review Queue ────────────────────────────────────

export interface ReviewQueueItem {
  position: number
  total: number
  message: Message
  contact: {
    id: string
    first_name: string | null
    last_name: string | null
    full_name: string
    job_title: string | null
    email_address: string | null
    linkedin_url: string | null
    contact_score: number | null
    icp_fit: string | null
    seniority_level: string | null
    department: string | null
    location_country: string | null
  }
  company: {
    id: string | null
    name: string | null
    domain: string | null
    tier: string | null
    industry: string | null
    hq_country: string | null
    summary: string | null
    status: string | null
  } | null
}

interface ReviewQueueResponse {
  queue: ReviewQueueItem[]
  stats: {
    total: number
    approved: number
    rejected: number
    draft: number
  }
}

export function useReviewQueue(campaignId: string | null, filters?: { status?: string; channel?: string; step?: string }) {
  return useQuery({
    queryKey: ['review-queue', campaignId, filters],
    queryFn: () => {
      const params: Record<string, string> = {}
      if (filters?.status) params.status = filters.status
      if (filters?.channel) params.channel = filters.channel
      if (filters?.step) params.step = filters.step
      return apiFetch<ReviewQueueResponse>(`/campaigns/${campaignId}/review-queue`, { params })
    },
    enabled: !!campaignId,
  })
}

// ── Review Summary ──────────────────────────────────

export interface ReviewSummary {
  total: number
  approved: number
  rejected: number
  draft: number
  excluded_contacts: number
  active_contacts: number
  by_channel: Record<string, Record<string, number>>
  can_approve_outreach: boolean
  pending_reason: string | null
}

export function useReviewSummary(campaignId: string | null) {
  return useQuery({
    queryKey: ['review-summary', campaignId],
    queryFn: () => apiFetch<ReviewSummary>(`/campaigns/${campaignId}/review-summary`),
    enabled: !!campaignId,
  })
}

// ── Regeneration ────────────────────────────────────

export interface RegenEstimate {
  estimated_cost: number
  input_tokens: number
  output_tokens: number
  model: string
}

export function useRegenEstimate(messageId: string | null) {
  return useQuery({
    queryKey: ['regen-estimate', messageId],
    queryFn: () => apiFetch<RegenEstimate>(`/messages/${messageId}/regenerate/estimate`),
    enabled: !!messageId,
  })
}

export function useRegenerateMessage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: {
      language?: string
      formality?: string
      tone?: string
      instruction?: string
    }}) =>
      apiFetch<Record<string, unknown>>(`/messages/${id}/regenerate`, {
        method: 'POST',
        body: data,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['review-queue'] })
      qc.invalidateQueries({ queryKey: ['messages'] })
      qc.invalidateQueries({ queryKey: ['review-summary'] })
    },
  })
}

// ── Disqualify Contact ──────────────────────────────

export function useDisqualifyContact() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ campaignId, contactId, scope, reason }: {
      campaignId: string
      contactId: string
      scope: 'campaign' | 'global'
      reason?: string
    }) =>
      apiFetch<{ ok: boolean; messages_rejected: number }>(
        `/campaigns/${campaignId}/disqualify-contact`,
        { method: 'POST', body: { contact_id: contactId, scope, reason } },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['review-queue'] })
      qc.invalidateQueries({ queryKey: ['messages'] })
      qc.invalidateQueries({ queryKey: ['review-summary'] })
      qc.invalidateQueries({ queryKey: ['campaign-contacts'] })
    },
  })
}
