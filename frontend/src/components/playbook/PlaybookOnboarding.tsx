import { useState } from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PlaybookOnboardingProps {
  onSkip: () => void
  /** Called when the user submits the form — triggers AI generation via chat */
  onGenerate: (payload: OnboardingPayload) => void
  /** True while the AI is streaming (disables resubmit) */
  isGenerating: boolean
}

export interface OnboardingPayload {
  domain: string
  objective: string
  icp: string
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PlaybookOnboarding({
  onSkip,
  onGenerate,
  isGenerating,
}: PlaybookOnboardingProps) {
  const [domain, setDomain] = useState('')
  const [objective, setObjective] = useState('')
  const [icp, setIcp] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!domain.trim() || !objective.trim() || isGenerating) return
    onGenerate({
      domain: domain.trim(),
      objective: objective.trim(),
      icp: icp.trim(),
    })
  }

  return (
    <div className="flex items-center justify-center h-full">
      <div className="w-full max-w-md p-8 rounded-xl border border-border-solid bg-surface">
        <h2 className="text-xl font-semibold text-text mb-1">
          Set Up Your Playbook
        </h2>
        <p className="text-sm text-text-muted mb-6">
          Answer a few questions and the AI will draft your GTM strategy
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="pb-domain"
              className="block text-sm font-medium text-text mb-1"
            >
              Company domain
            </label>
            <input
              id="pb-domain"
              type="text"
              required
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="yourcompany.com"
              disabled={isGenerating}
              className="w-full px-3 py-2 text-sm rounded-md border border-border-solid bg-surface-alt text-text placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-accent/40 disabled:opacity-50"
            />
          </div>

          <div>
            <label
              htmlFor="pb-objective"
              className="block text-sm font-medium text-text mb-1"
            >
              Primary objective
            </label>
            <textarea
              id="pb-objective"
              required
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="e.g., Generate enterprise leads in DACH region"
              rows={2}
              disabled={isGenerating}
              className="w-full px-3 py-2 text-sm rounded-md border border-border-solid bg-surface-alt text-text placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-accent/40 resize-none disabled:opacity-50"
            />
          </div>

          <div>
            <label
              htmlFor="pb-icp"
              className="block text-sm font-medium text-text mb-1"
            >
              Ideal customer profile
              <span className="ml-1 text-text-dim font-normal">(optional)</span>
            </label>
            <textarea
              id="pb-icp"
              value={icp}
              onChange={(e) => setIcp(e.target.value)}
              placeholder="e.g., B2B SaaS companies, 50-500 employees, VP of Engineering or CTO"
              rows={2}
              disabled={isGenerating}
              className="w-full px-3 py-2 text-sm rounded-md border border-border-solid bg-surface-alt text-text placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-accent/40 resize-none disabled:opacity-50"
            />
          </div>

          <button
            type="submit"
            disabled={isGenerating || !domain.trim() || !objective.trim()}
            className="w-full py-2 px-4 text-sm font-medium rounded-md bg-accent text-white hover:bg-accent-hover transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {isGenerating ? 'Generating...' : 'Generate Strategy'}
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
