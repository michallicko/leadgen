/**
 * useWorkflowStatus — derives GTM workflow phase from onboarding status.
 *
 * Phases: Strategy > Contacts > Enrich > Messages > Campaign
 * Compute-on-read from the existing onboarding-status endpoint.
 */

import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import type { OnboardingStatus } from './useOnboarding'

export type WorkflowPhase =
  | 'strategy'
  | 'contacts'
  | 'enrich'
  | 'messages'
  | 'campaign'

export interface WorkflowStatus {
  currentPhase: WorkflowPhase
  completedPhases: WorkflowPhase[]
}

const PHASES: WorkflowPhase[] = [
  'strategy',
  'contacts',
  'enrich',
  'messages',
  'campaign',
]

function deriveWorkflowStatus(status: OnboardingStatus): WorkflowStatus {
  const completed: WorkflowPhase[] = []

  if (status.has_strategy) {
    completed.push('strategy')
  }
  if (status.contact_count > 0) {
    completed.push('contacts')
  }
  if (status.campaign_count > 0) {
    completed.push('messages')
    completed.push('campaign')
  }

  // Current phase = first incomplete phase
  const currentPhase =
    PHASES.find((p) => !completed.includes(p)) || 'campaign'

  return { currentPhase, completedPhases: completed }
}

export function useWorkflowStatus() {
  return useQuery({
    queryKey: ['workflow-status'],
    queryFn: async () => {
      const status = await apiFetch<OnboardingStatus>(
        '/tenants/onboarding-status'
      )
      return deriveWorkflowStatus(status)
    },
    staleTime: 30_000,
  })
}

export { PHASES }
