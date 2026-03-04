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

/** Map backend workflow_phase to the high-level GTM phase. */
const BACKEND_PHASE_MAP: Record<string, WorkflowPhase> = {
  no_strategy: 'strategy',
  strategy_draft: 'strategy',
  strategy_ready: 'contacts',
  contacts_imported: 'enrich',
  enrichment_running: 'enrich',
  enrichment_done: 'messages',
  qualified_reviewed: 'messages',
  messages_generated: 'messages',
  messages_approved: 'campaign',
  campaign_created: 'campaign',
  campaign_launched: 'campaign',
}

function deriveWorkflowStatus(status: OnboardingStatus): WorkflowStatus {
  const completed: WorkflowPhase[] = []

  if (status.has_strategy) {
    completed.push('strategy')
  }
  if (status.contact_count > 0) {
    completed.push('contacts')
  }

  // Use backend workflow_phase for enrichment completion detection
  const backendPhase = (status as Record<string, unknown>).workflow_phase as string | undefined
  if (backendPhase) {
    const mapped = BACKEND_PHASE_MAP[backendPhase]
    if (mapped) {
      // Mark all phases up to (but not including) the current mapped phase as completed
      const idx = PHASES.indexOf(mapped)
      for (let i = 0; i < idx; i++) {
        if (!completed.includes(PHASES[i])) {
          completed.push(PHASES[i])
        }
      }
    }
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
