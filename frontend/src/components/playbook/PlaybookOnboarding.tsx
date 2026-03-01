import { useState } from 'react'
import { WizardSteps } from '../ui/WizardSteps'
import { TemplateSelector } from './TemplateSelector'
import { useApplyStrategyTemplate } from '../../api/queries/useStrategyTemplates'

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
  templateId?: string | null
}

// ---------------------------------------------------------------------------
// Steps
// ---------------------------------------------------------------------------

const WIZARD_STEPS = [
  { label: 'Discovery' },
  { label: 'Template' },
  { label: 'Generate' },
]

// ---------------------------------------------------------------------------
// Loading overlay for AI merge
// ---------------------------------------------------------------------------

function TemplateMergeOverlay() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-surface border border-border-solid rounded-xl shadow-xl p-8 max-w-md mx-4 text-center">
        <div className="w-10 h-10 mx-auto mb-4 border-2 border-border border-t-accent rounded-full animate-spin" />
        <h3 className="text-base font-semibold text-text mb-2">
          Personalizing your strategy
        </h3>
        <p className="text-sm text-text-muted">
          Merging template with your business context...
        </p>
        <p className="text-xs text-text-dim mt-3">
          This usually takes 5-15 seconds
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PlaybookOnboarding({
  onSkip,
  onGenerate,
  isGenerating,
}: PlaybookOnboardingProps) {
  const [step, setStep] = useState(0) // 0: discovery, 1: template
  const [domain, setDomain] = useState('')
  const [objective, setObjective] = useState('')
  const [icp, setIcp] = useState('')
  const applyTemplate = useApplyStrategyTemplate()

  const handleDiscoverySubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!domain.trim() || !objective.trim()) return
    setStep(1) // Move to template selection
  }

  const handleTemplateSelect = async (templateId: string | null) => {
    if (templateId) {
      // Apply template via AI merge, then exit onboarding
      try {
        await applyTemplate.mutateAsync(templateId)
        onGenerate({
          domain: domain.trim(),
          objective: objective.trim(),
          icp: icp.trim(),
          templateId,
        })
      } catch {
        // Failed — fall back to normal generation
        onGenerate({
          domain: domain.trim(),
          objective: objective.trim(),
          icp: icp.trim(),
        })
      }
    } else {
      // Blank slate — generate via chat
      onGenerate({
        domain: domain.trim(),
        objective: objective.trim(),
        icp: icp.trim(),
      })
    }
  }

  // ---------------------------------------------------------------------------
  // Step 0: Discovery questions
  // ---------------------------------------------------------------------------

  if (step === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-full max-w-md p-8 rounded-xl border border-border-solid bg-surface">
          <div className="mb-6">
            <WizardSteps steps={WIZARD_STEPS} current={0} />
          </div>

          <h2 className="text-xl font-semibold text-text mb-1">
            Set Up Your Playbook
          </h2>
          <p className="text-sm text-text-muted mb-6">
            Answer a few questions and the AI will draft your GTM strategy
          </p>

          <form onSubmit={handleDiscoverySubmit} className="space-y-4">
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
              Next: Choose a template
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

  // ---------------------------------------------------------------------------
  // Step 1: Template selection
  // ---------------------------------------------------------------------------

  return (
    <div className="flex items-center justify-center h-full">
      <div className="w-full max-w-2xl p-8 rounded-xl border border-border-solid bg-surface">
        <div className="mb-6">
          <WizardSteps steps={WIZARD_STEPS} current={1} />
        </div>

        <TemplateSelector
          onSelect={handleTemplateSelect}
          onBack={() => setStep(0)}
          isApplying={applyTemplate.isPending || isGenerating}
        />

        {applyTemplate.isPending && <TemplateMergeOverlay />}
      </div>
    </div>
  )
}
