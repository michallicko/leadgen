import { useState } from 'react'
import { useParams } from 'react-router'
import { useTenantBySlug } from '../../api/queries/useAdmin'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PlaybookOnboardingProps {
  onSkip: () => void
  /** Called when the user submits the form -- triggers AI generation + research */
  onGenerate: (payload: OnboardingPayload) => void
  /** True while the AI is streaming (disables resubmit) */
  isGenerating: boolean
  /** Open the template selector (optional — if not provided, "Browse Templates" link is hidden) */
  onBrowseTemplates?: () => void
}

export interface OnboardingPayload {
  domains: string[]
  description: string
  challenge_type: string
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PlaybookOnboarding({
  onSkip,
  onGenerate,
  isGenerating,
  onBrowseTemplates,
}: PlaybookOnboardingProps) {
  const { namespace } = useParams<{ namespace: string }>()
  const { tenant } = useTenantBySlug(namespace)

  const [objective, setObjective] = useState('')

  const isValid = objective.trim().length > 0

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!isValid || isGenerating) return

    // Auto-resolve domains from tenant config
    const domains = tenant?.domain ? [tenant.domain] : []

    onGenerate({
      domains,
      description: objective.trim(),
      // AI infers the challenge from the objective
      challenge_type: 'auto',
    })
  }

  const detectedDomain = tenant?.domain

  return (
    <div className="w-full max-w-lg mx-auto mt-12 mb-8">
      <div className="rounded-xl border border-border-solid bg-surface p-6 shadow-sm">
        {/* Welcome header */}
        <div className="mb-5">
          <h2 className="text-lg font-semibold text-text mb-1">
            Generate Your GTM Strategy
          </h2>
          <p className="text-sm text-text-muted">
            Tell us your go-to-market objective and the AI will research your
            market and draft a complete strategy playbook.
          </p>
        </div>

        {/* Auto-detected domain info */}
        {detectedDomain && (
          <div className="flex items-center gap-2 mb-4 px-3 py-2 rounded-md bg-surface-alt border border-border text-sm">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-accent-cyan flex-shrink-0"
            >
              <circle cx="12" cy="12" r="10" />
              <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            </svg>
            <span className="text-text-muted">Company domain:</span>
            <span className="font-medium text-text">{detectedDomain}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* GTM Objective */}
          <div>
            <label
              htmlFor="pb-objective"
              className="block text-sm font-medium text-text mb-1"
            >
              What is your GTM objective?
            </label>
            <textarea
              id="pb-objective"
              required
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="e.g., Generate qualified B2B leads for our SaaS product, Book demos with enterprise CTOs, Expand into the DACH market..."
              rows={3}
              disabled={isGenerating}
              className="w-full px-3 py-2 text-sm rounded-md border border-border-solid bg-surface-alt text-text placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-accent/40 resize-none disabled:opacity-50"
              autoFocus
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={isGenerating || !isValid}
            className="w-full py-2.5 px-4 text-sm font-medium rounded-md bg-accent text-white hover:bg-accent-hover transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {isGenerating ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Generating...
              </span>
            ) : (
              'Get Started'
            )}
          </button>
        </form>

        <div className="mt-3 flex items-center justify-center gap-4">
          {onBrowseTemplates && (
            <button
              type="button"
              onClick={onBrowseTemplates}
              className="text-sm text-text-muted hover:text-text transition-colors bg-transparent border-none cursor-pointer p-0"
            >
              Browse templates
            </button>
          )}
          <button
            type="button"
            onClick={onSkip}
            className="text-sm text-accent hover:text-accent-hover transition-colors bg-transparent border-none cursor-pointer p-0"
          >
            I'll write it myself &rarr;
          </button>
        </div>
      </div>
    </div>
  )
}
