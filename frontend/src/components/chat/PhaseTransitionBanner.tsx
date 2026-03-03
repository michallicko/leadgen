/**
 * PhaseTransitionBanner -- shows when the current workflow phase is complete
 * and the user can advance to the next phase.
 *
 * Displays a compact, dismissible banner with:
 * - Completion message for the current phase
 * - CTA button that auto-navigates to the next phase's page
 *
 * BL-170: Auto-Phase Transitions Between Workflow Steps
 */

import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { usePhaseTransition } from '../../hooks/usePhaseTransition'

function CheckCircleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="8" r="6.5" />
      <path d="M5.5 8l2 2 3.5-3.5" />
    </svg>
  )
}

function ArrowRightIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4.5 2.5l3.5 3.5-3.5 3.5" />
    </svg>
  )
}

export function PhaseTransitionBanner() {
  const { namespace } = useParams<{ namespace: string }>()
  const navigate = useNavigate()
  const { data, isLoading } = usePhaseTransition()
  const [dismissed, setDismissed] = useState(false)

  if (isLoading || !data || !data.transition.ready || dismissed) return null

  const { transition } = data

  return (
    <div className="mx-3 my-1.5 flex-shrink-0">
      <div className="bg-accent-cyan/10 border border-accent-cyan/30 rounded-lg px-3 py-2">
        <div className="flex items-start gap-2">
          <span className="text-accent-cyan flex-shrink-0 mt-0.5">
            <CheckCircleIcon />
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-text leading-snug">
              {transition.message}
            </p>
            {transition.next_phase_label && (
              <p className="text-[11px] text-text-muted mt-0.5">
                Ready to move to: {transition.next_phase_label}
              </p>
            )}
          </div>
          <button
            onClick={() => setDismissed(true)}
            className="flex-shrink-0 w-4 h-4 flex items-center justify-center text-text-dim hover:text-text-muted transition-colors bg-transparent border-none cursor-pointer"
            aria-label="Dismiss"
          >
            <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M1.5 1.5l5 5M6.5 1.5l-5 5" />
            </svg>
          </button>
        </div>
        <button
          onClick={() => {
            if (namespace && transition.cta_path) {
              navigate(`/${namespace}${transition.cta_path}`)
            }
          }}
          className="mt-1.5 flex items-center gap-1 text-[11px] font-semibold text-accent-cyan hover:text-accent-cyan/80 bg-transparent border-none cursor-pointer px-0 transition-colors"
        >
          {transition.cta_label}
          <ArrowRightIcon />
        </button>
      </div>
    </div>
  )
}
