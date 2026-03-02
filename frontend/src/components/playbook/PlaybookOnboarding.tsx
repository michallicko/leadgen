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
}: PlaybookOnboardingProps) {
  const { namespace } = useParams<{ namespace: string }>()
  const { tenant } = useTenantBySlug(namespace)

  const [description, setDescription] = useState('')

  const isValid = description.trim().length > 0

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!isValid || isGenerating) return

    // Auto-resolve domains from tenant config
    const domains = tenant?.domain ? [tenant.domain] : []

    onGenerate({
      domains,
      description: description.trim(),
      // AI infers the challenge from the description
      challenge_type: 'auto',
    })
  }

  return (
    <div className="flex items-center justify-center h-full">
      <div className="w-full max-w-md p-8 rounded-xl border border-border-solid bg-surface">
        <h2 className="text-xl font-semibold text-text mb-1">
          Generate Your GTM Strategy
        </h2>
        <p className="text-sm text-text-muted mb-6">
          Describe your business and the AI will research your market and
          draft a complete strategy playbook.
        </p>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Business description */}
          <div>
            <label
              htmlFor="pb-description"
              className="block text-sm font-medium text-text mb-1"
            >
              What does your business do?
            </label>
            <textarea
              id="pb-description"
              required
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g., We sell marketing automation software to mid-market B2B SaaS companies in Europe..."
              rows={4}
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
              'Generate My Strategy'
            )}
          </button>
        </form>

        <div className="mt-4 text-center">
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
