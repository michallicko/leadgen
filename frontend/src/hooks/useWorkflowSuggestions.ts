/**
 * Hook for fetching proactive workflow suggestions.
 *
 * Calls GET /api/tenants/workflow-suggestions to get context-aware next-step
 * suggestions based on the namespace's current workflow state (strategy,
 * contacts, enrichment, campaigns, messages).
 *
 * BL-135: Proactive Next-Step Suggestions
 * BL-169: Event-Driven Chat Nudges
 */

import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'

export interface WorkflowSuggestion {
  id: string
  icon: 'strategy' | 'contacts' | 'enrich' | 'campaign' | 'messages'
  summary: string
  detail: string
  action_label: string
  action_path: string
  action_type?: 'navigate' | 'navigate_and_act'
  nudge_type?: 'step' | 'event'
  priority: number
}

interface WorkflowSuggestionsResponse {
  suggestions: WorkflowSuggestion[]
  nudge_count: number
}

export function useWorkflowSuggestions(enabled = true) {
  return useQuery({
    queryKey: ['workflow-suggestions'],
    queryFn: () =>
      apiFetch<WorkflowSuggestionsResponse>('/tenants/workflow-suggestions'),
    staleTime: 30_000, // Refresh every 30 seconds (faster for nudges)
    enabled,
    select: (data) => data.suggestions,
  })
}

/** Return the nudge count for notification badge display. */
export function useNudgeCount(enabled = true) {
  return useQuery({
    queryKey: ['workflow-suggestions'],
    queryFn: () =>
      apiFetch<WorkflowSuggestionsResponse>('/tenants/workflow-suggestions'),
    staleTime: 30_000,
    enabled,
    select: (data) => data.nudge_count,
  })
}
