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
  contact: MessageContact
  company: MessageCompany | null
}

interface MessagesResponse {
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
