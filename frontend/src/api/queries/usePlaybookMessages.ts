/**
 * React Query hooks for playbook messages phase endpoints (BL-118).
 *
 * Endpoints:
 * - POST /api/playbook/:id/messages/setup
 * - POST /api/playbook/:id/generate-messages
 * - GET  /api/playbook/:id/messages
 * - PATCH /api/playbook/:id/messages/:messageId
 * - POST /api/playbook/:id/messages/batch
 * - POST /api/playbook/:id/confirm-messages
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'

// ── Types ──────────────────────────────────────────

export interface SetupCampaignResponse {
  campaign_id: string
  campaign_name: string
  campaign_status: string
  total_contacts: number
  contacts_added: number
  created: boolean
}

export interface PlaybookMessage {
  id: string
  contact_id: string
  contact: {
    full_name: string
    job_title?: string
    email?: string
  }
  company?: {
    name: string
    domain?: string
  } | null
  subject: string | null
  body: string
  status: string
  channel: string
  sequence_step: number
  created_at: string | null
}

export interface PlaybookMessagesResponse {
  messages: PlaybookMessage[]
  total: number
  page: number
  per_page: number
  campaign_id: string | null
  campaign_status: string | null
  status_counts: Record<string, number>
}

export interface PlaybookMessageFilters {
  status?: string
  page?: number
  per_page?: number
  enabled?: boolean
}

interface GenerateMessagesResponse {
  campaign_id: string
  status: string
  total_contacts: number
}

interface UpdateMessageResponse {
  id: string
  status: string
  body: string
  subject: string | null
  updated: boolean
}

interface BatchUpdateResponse {
  updated: number
  status: string
}

interface ConfirmMessagesResponse {
  confirmed: boolean
  approved_count: number
  phase: string
  campaign_status: string
  campaign_id: string
}

// ── Hooks ──────────────────────────────────────────

/**
 * Auto-create or load campaign for the playbook.
 * Called once when the Messages phase mounts.
 */
export function useSetupCampaign(playbookId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiFetch<SetupCampaignResponse>(
        `/playbook/${playbookId}/messages/setup`,
        { method: 'POST' },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook'] })
      qc.invalidateQueries({ queryKey: ['playbook', playbookId, 'messages'] })
    },
  })
}

export function usePlaybookMessages(
  playbookId: string | undefined,
  filters: PlaybookMessageFilters = {},
) {
  const params: Record<string, string> = {}
  if (filters.status) params.status = filters.status
  if (filters.page) params.page = String(filters.page)
  if (filters.per_page) params.per_page = String(filters.per_page)

  return useQuery({
    queryKey: ['playbook', playbookId, 'messages', filters],
    queryFn: () =>
      apiFetch<PlaybookMessagesResponse>(
        `/playbook/${playbookId}/messages`,
        { params },
      ),
    enabled: !!playbookId && (filters.enabled !== false),
    refetchInterval: (query) => {
      const data = query.state.data
      if (data?.campaign_status === 'generating') return 3000
      return false
    },
  })
}

export function useGenerateMessages(playbookId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiFetch<GenerateMessagesResponse>(
        `/playbook/${playbookId}/generate-messages`,
        { method: 'POST' },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook', playbookId, 'messages'] })
    },
  })
}

export function useUpdatePlaybookMessage(playbookId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      messageId,
      data,
    }: {
      messageId: string
      data: { status?: string; body?: string; subject?: string }
    }) =>
      apiFetch<UpdateMessageResponse>(
        `/playbook/${playbookId}/messages/${messageId}`,
        { method: 'PATCH', body: data },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook', playbookId, 'messages'] })
    },
  })
}

export function useBatchUpdatePlaybookMessages(
  playbookId: string | undefined,
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { action: 'approve_all' | 'reject_all' }) =>
      apiFetch<BatchUpdateResponse>(
        `/playbook/${playbookId}/messages/batch`,
        { method: 'POST', body: data },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook', playbookId, 'messages'] })
    },
  })
}

export function useConfirmMessages(playbookId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiFetch<ConfirmMessagesResponse>(
        `/playbook/${playbookId}/confirm-messages`,
        { method: 'POST' },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook'] })
    },
  })
}
