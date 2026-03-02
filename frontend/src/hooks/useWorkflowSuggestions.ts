/**
 * Hook for fetching proactive workflow suggestions.
 *
 * Calls GET /api/tenants/workflow-suggestions to get context-aware next-step
 * suggestions based on the namespace's current workflow state (strategy,
 * contacts, enrichment, campaigns, messages).
 *
 * BL-135: Proactive Next-Step Suggestions
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
  priority: number
}

interface WorkflowSuggestionsResponse {
  suggestions: WorkflowSuggestion[]
}

export function useWorkflowSuggestions(enabled = true) {
  return useQuery({
    queryKey: ['workflow-suggestions'],
    queryFn: () =>
      apiFetch<WorkflowSuggestionsResponse>('/tenants/workflow-suggestions'),
    staleTime: 60_000, // Refresh every minute
    enabled,
    select: (data) => data.suggestions,
  })
}
