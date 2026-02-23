import { useState, useEffect } from 'react'
import { useResearchStatus, useTriggerResearch } from '../../api/queries/usePlaybook'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PlaybookOnboardingProps {
  onSkip: () => void
  onComplete: () => void
}

// ---------------------------------------------------------------------------
// Progress stage helpers
// ---------------------------------------------------------------------------

type StageState = 'pending' | 'active' | 'completed'

function StageIndicator({ state }: { state: StageState }) {
  if (state === 'completed') {
    return (
      <div className="w-6 h-6 rounded-full bg-success/20 text-success flex items-center justify-center flex-shrink-0">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 7l3 3 5-5" />
        </svg>
      </div>
    )
  }
  if (state === 'active') {
    return (
      <div className="w-6 h-6 flex items-center justify-center flex-shrink-0">
        <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }
  return (
    <div className="w-6 h-6 rounded-full border-2 border-border-solid flex-shrink-0" />
  )
}

function deriveStages(companyStatus: string | undefined): [StageState, StageState] {
  if (!companyStatus) return ['active', 'pending']

  const s = companyStatus.toLowerCase()
  // L1 in progress
  if (s === 'new' || s === 'enrichment_started' || s === 'enrichment_failed') {
    return ['active', 'pending']
  }
  // L1 done, L2 in progress
  if (s === 'triage_passed' || s === 'l2_started' || s === 'triage_review' || s === 'disqualified') {
    return ['completed', 'active']
  }
  // Both done
  if (s === 'enriched_l2' || s === 'enrichment_l2_failed') {
    return ['completed', 'completed']
  }
  // Fallback
  return ['active', 'pending']
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PlaybookOnboarding({ onSkip, onComplete }: PlaybookOnboardingProps) {
  const [triggered, setTriggered] = useState(false)
  const [domain, setDomain] = useState('')
  const [objective, setObjective] = useState('')

  const triggerMutation = useTriggerResearch()
  const researchQuery = useResearchStatus(triggered)

  // Auto-complete when research finishes
  useEffect(() => {
    if (researchQuery.data?.status === 'completed') {
      onComplete()
    }
  }, [researchQuery.data?.status, onComplete])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!domain.trim() || !objective.trim()) return

    triggerMutation.mutate(
      { domain: domain.trim(), objective: objective.trim() },
      { onSuccess: () => setTriggered(true) },
    )
  }

  // ---------------------------------------------------------------------------
  // State 2: Research progress
  // ---------------------------------------------------------------------------

  if (triggered) {
    const company = researchQuery.data?.company
    const [stage1, stage2] = deriveStages(company?.status)

    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-full max-w-md p-8 rounded-xl border border-border-solid bg-surface">
          {/* Company header */}
          {company && (
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-text">{company.name}</h2>
              <p className="text-sm text-text-muted">{company.domain}</p>
            </div>
          )}
          {!company && (
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-text">Researching...</h2>
              <p className="text-sm text-text-muted">{domain}</p>
            </div>
          )}

          {/* Progress stages */}
          <div className="space-y-4 mb-6">
            <div className="flex items-center gap-3">
              <StageIndicator state={stage1} />
              <div>
                <p className="text-sm font-medium text-text">Company Profile</p>
                <p className="text-xs text-text-dim">Basic company info and market signals</p>
              </div>
            </div>

            {/* Connector line */}
            <div className="ml-3 w-px h-4 bg-border-solid" />

            <div className="flex items-center gap-3">
              <StageIndicator state={stage2} />
              <div>
                <p className="text-sm font-medium text-text">Deep Analysis</p>
                <p className="text-xs text-text-dim">Competitive landscape and strategic insights</p>
              </div>
            </div>
          </div>

          <p className="text-xs text-text-dim mb-4">This usually takes 1-2 minutes</p>

          <button
            type="button"
            onClick={onSkip}
            className="text-sm text-accent hover:text-accent-hover transition-colors bg-transparent border-none cursor-pointer p-0"
          >
            Skip and start editing &rarr;
          </button>
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // State 1: Setup form
  // ---------------------------------------------------------------------------

  return (
    <div className="flex items-center justify-center h-full">
      <div className="w-full max-w-md p-8 rounded-xl border border-border-solid bg-surface">
        <h2 className="text-xl font-semibold text-text mb-1">Set Up Your Playbook</h2>
        <p className="text-sm text-text-muted mb-6">
          We'll research your company to personalize your GTM strategy
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="pb-domain" className="block text-sm font-medium text-text mb-1">
              Company domain
            </label>
            <input
              id="pb-domain"
              type="text"
              required
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="yourcompany.com"
              className="w-full px-3 py-2 text-sm rounded-md border border-border-solid bg-surface-alt text-text placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
          </div>

          <div>
            <label htmlFor="pb-objective" className="block text-sm font-medium text-text mb-1">
              Primary objective
            </label>
            <textarea
              id="pb-objective"
              required
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="e.g., Generate enterprise leads in DACH region"
              rows={3}
              className="w-full px-3 py-2 text-sm rounded-md border border-border-solid bg-surface-alt text-text placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-accent/40 resize-none"
            />
          </div>

          <button
            type="submit"
            disabled={triggerMutation.isPending || !domain.trim() || !objective.trim()}
            className="w-full py-2 px-4 text-sm font-medium rounded-md bg-accent text-white hover:bg-accent-hover transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {triggerMutation.isPending ? 'Starting...' : 'Start Research'}
          </button>
        </form>

        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={onSkip}
            className="text-sm text-accent hover:text-accent-hover transition-colors bg-transparent border-none cursor-pointer p-0"
          >
            Skip to Editor &rarr;
          </button>
        </div>
      </div>
    </div>
  )
}
