/**
 * WelcomeBackBanner -- shown when a user returns after >1 hour.
 *
 * Displays a compact, dismissible banner in the chat panel with:
 * - "Welcome back!" greeting
 * - Context about last session (which workflow phase they were in)
 * - Quick-action buttons based on current workflow state
 *
 * Persistence:
 * - `last_active_at` tracked in localStorage, updated every 60s
 * - Banner shows once per session (dismissed state stored in sessionStorage)
 * - Quick actions use the same workflow suggestions endpoint
 *
 * BL-179: Re-Engagement Prompts -- Session-to-Session Continuity
 */

import { useState, useEffect, useMemo, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useWorkflowStatus, type WorkflowPhase } from '../../hooks/useWorkflowStatus'
import { useWorkflowSuggestions, type WorkflowSuggestion } from '../../hooks/useWorkflowSuggestions'

// ---------------------------------------------------------------------------
// localStorage keys
// ---------------------------------------------------------------------------

const LAST_ACTIVE_KEY = 'leadgen_last_active_at'
const LAST_PHASE_KEY = 'leadgen_last_phase'
const DISMISSED_KEY = 'leadgen_welcome_back_dismissed'

// Minimum gap (ms) before showing the banner: 1 hour
const MIN_GAP_MS = 60 * 60 * 1000

// How often to update the last_active_at timestamp (ms): every 60s
const ACTIVITY_TICK_MS = 60_000

// ---------------------------------------------------------------------------
// Phase labels for display
// ---------------------------------------------------------------------------

const PHASE_LABELS: Record<WorkflowPhase, string> = {
  strategy: 'Strategy',
  contacts: 'Contacts',
  enrich: 'Enrichment',
  messages: 'Messages',
  campaign: 'Campaign',
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function WelcomeBackBanner() {
  const { namespace } = useParams<{ namespace: string }>()
  const navigate = useNavigate()
  const { data: workflowStatus } = useWorkflowStatus()
  const { data: suggestions } = useWorkflowSuggestions()

  const [shouldShow, setShouldShow] = useState(false)
  const [lastPhase, setLastPhase] = useState<string | null>(null)
  const [dismissed, setDismissed] = useState(false)

  // ---------------------------------------------------------------------------
  // Detect return after absence
  // ---------------------------------------------------------------------------

  useEffect(() => {
    // Check if already dismissed this session
    try {
      if (sessionStorage.getItem(DISMISSED_KEY) === 'true') {
        setDismissed(true)
        return
      }
    } catch {
      // sessionStorage unavailable
    }

    // Read last active timestamp
    try {
      const lastActiveStr = localStorage.getItem(LAST_ACTIVE_KEY)
      const storedPhase = localStorage.getItem(LAST_PHASE_KEY)

      if (lastActiveStr) {
        const lastActive = parseInt(lastActiveStr, 10)
        const gap = Date.now() - lastActive
        if (gap >= MIN_GAP_MS) {
          setShouldShow(true)
          setLastPhase(storedPhase)
        }
      }
    } catch {
      // localStorage unavailable
    }

    // Update last active immediately
    try {
      localStorage.setItem(LAST_ACTIVE_KEY, String(Date.now()))
    } catch {
      // ignore
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Periodically update last_active_at and current phase
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const timer = setInterval(() => {
      try {
        localStorage.setItem(LAST_ACTIVE_KEY, String(Date.now()))
        if (workflowStatus?.currentPhase) {
          localStorage.setItem(LAST_PHASE_KEY, workflowStatus.currentPhase)
        }
      } catch {
        // ignore
      }
    }, ACTIVITY_TICK_MS)

    return () => clearInterval(timer)
  }, [workflowStatus?.currentPhase])

  // Also update phase on workflow status change
  useEffect(() => {
    if (workflowStatus?.currentPhase) {
      try {
        localStorage.setItem(LAST_PHASE_KEY, workflowStatus.currentPhase)
      } catch {
        // ignore
      }
    }
  }, [workflowStatus?.currentPhase])

  // ---------------------------------------------------------------------------
  // Quick actions (up to 2 from suggestions)
  // ---------------------------------------------------------------------------

  const quickActions = useMemo(() => {
    if (!suggestions) return []
    return suggestions.slice(0, 2)
  }, [suggestions])

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handleDismiss = useCallback(() => {
    setDismissed(true)
    try {
      sessionStorage.setItem(DISMISSED_KEY, 'true')
    } catch {
      // ignore
    }
  }, [])

  const handleAction = useCallback((suggestion: WorkflowSuggestion) => {
    handleDismiss()
    if (namespace && suggestion.action_path) {
      navigate(`/${namespace}${suggestion.action_path}`)
    }
  }, [namespace, navigate, handleDismiss])

  const handlePickUp = useCallback(() => {
    handleDismiss()
    // Navigate to the current workflow phase page
    if (namespace && workflowStatus?.currentPhase) {
      const phasePages: Record<WorkflowPhase, string> = {
        strategy: '/playbook',
        contacts: '/contacts',
        enrich: '/enrich',
        messages: '/messages',
        campaign: '/campaigns',
      }
      navigate(`/${namespace}${phasePages[workflowStatus.currentPhase]}`)
    }
  }, [namespace, workflowStatus?.currentPhase, navigate, handleDismiss])

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (!shouldShow || dismissed) return null

  const currentPhaseLabel = workflowStatus?.currentPhase
    ? PHASE_LABELS[workflowStatus.currentPhase]
    : null

  const lastPhaseLabel = lastPhase && lastPhase in PHASE_LABELS
    ? PHASE_LABELS[lastPhase as WorkflowPhase]
    : null

  return (
    <div className="mx-3 my-1.5 flex-shrink-0">
      <div className="bg-accent/10 border border-accent/30 rounded-lg px-3 py-2.5">
        {/* Header row */}
        <div className="flex items-start gap-2">
          <span className="text-accent flex-shrink-0 mt-0.5">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8 1a5 5 0 013.5 8.5L8 13l-3.5-3.5A5 5 0 018 1z" />
              <circle cx="8" cy="6" r="1.5" />
            </svg>
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-text leading-snug">
              Welcome back!
            </p>
            <p className="text-[11px] text-text-muted mt-0.5">
              {lastPhaseLabel
                ? `Last session: working on ${lastPhaseLabel} phase.`
                : 'Pick up where you left off.'}
              {currentPhaseLabel && currentPhaseLabel !== lastPhaseLabel && (
                <> Current focus: <span className="font-medium text-text">{currentPhaseLabel}</span>.</>
              )}
            </p>
          </div>
          <button
            onClick={handleDismiss}
            className="flex-shrink-0 w-4 h-4 flex items-center justify-center text-text-dim hover:text-text-muted transition-colors bg-transparent border-none cursor-pointer"
            aria-label="Dismiss"
          >
            <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M1.5 1.5l5 5M6.5 1.5l-5 5" />
            </svg>
          </button>
        </div>

        {/* Quick actions */}
        <div className="flex items-center gap-1.5 mt-2">
          <button
            onClick={handlePickUp}
            className="text-[11px] font-semibold text-accent hover:text-accent-hover bg-transparent border-none cursor-pointer px-0 transition-colors"
          >
            Continue {currentPhaseLabel ?? 'working'}
          </button>

          {quickActions.map((s) => (
            <button
              key={s.id}
              onClick={() => handleAction(s)}
              className="text-[11px] px-2 py-0.5 rounded-full bg-surface border border-border text-text-muted hover:text-text hover:border-accent cursor-pointer transition-colors"
            >
              {s.action_label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
