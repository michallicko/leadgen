import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'
import type { MessageFilters, MessagesResponse } from './useMessages'

export type { Message } from './useMessages'

// ── Campaign messages query with filter params ──────────

export interface CampaignMessageFilters {
  status?: string
  channel?: string
  step?: string
  search?: string
}

/**
 * Fetch messages for a specific campaign with optional filters.
 * Wraps the existing /messages endpoint with campaign_id pre-set.
 */
export function useCampaignMessages(campaignId: string | null, filters: CampaignMessageFilters = {}) {
  const queryFilters: MessageFilters = {
    campaign_id: campaignId ?? undefined,
    status: filters.status || undefined,
    channel: filters.channel || undefined,
  }

  return useQuery({
    queryKey: ['campaign-messages', campaignId, filters],
    queryFn: () => {
      const params: Record<string, string> = {}
      if (queryFilters.campaign_id) params.campaign_id = queryFilters.campaign_id
      if (queryFilters.status) params.status = queryFilters.status
      if (queryFilters.channel) params.channel = queryFilters.channel
      return apiFetch<MessagesResponse>('/messages', { params })
    },
    enabled: !!campaignId,
  })
}

// ── Batch action (approve/reject) mutation ──────────────

interface BatchActionRequest {
  campaignId: string
  messageIds: string[]
  action: 'approve' | 'reject'
  reason?: string
}

interface BatchActionResponse {
  updated: number
  action: string
}

/**
 * Batch approve or reject messages for a campaign.
 * Uses the campaign-scoped batch-action endpoint.
 */
export function useBatchAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ campaignId, messageIds, action, reason }: BatchActionRequest) =>
      apiFetch<BatchActionResponse>(
        `/campaigns/${campaignId}/messages/batch-action`,
        {
          method: 'POST',
          body: { message_ids: messageIds, action, reason },
        },
      ),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['campaign-messages', vars.campaignId] })
      qc.invalidateQueries({ queryKey: ['messages'] })
      qc.invalidateQueries({ queryKey: ['review-queue', vars.campaignId] })
      qc.invalidateQueries({ queryKey: ['review-summary', vars.campaignId] })
      qc.invalidateQueries({ queryKey: ['campaign', vars.campaignId] })
    },
  })
}
