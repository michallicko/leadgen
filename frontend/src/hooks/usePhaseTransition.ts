/**
 * usePhaseTransition -- detects when the current workflow phase is complete
 * and a transition to the next phase is available.
 *
 * BL-170: Auto-Phase Transitions Between Workflow Steps
 */

import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'

export interface PhaseTransition {
  ready: boolean
  next_phase?: string
  next_phase_label?: string
  cta_label?: string
  cta_path?: string
  message?: string
}

interface PhaseTransitionResponse {
  current_phase: string
  current_phase_label: string
  progress_pct: number
  transition: PhaseTransition
}

export function usePhaseTransition(enabled = true) {
  return useQuery({
    queryKey: ['phase-transition'],
    queryFn: () =>
      apiFetch<PhaseTransitionResponse>('/tenants/phase-transition'),
    staleTime: 30_000,
    enabled,
    select: (data) => ({
      currentPhase: data.current_phase,
      currentPhaseLabel: data.current_phase_label,
      progressPct: data.progress_pct,
      transition: data.transition,
    }),
  })
}
