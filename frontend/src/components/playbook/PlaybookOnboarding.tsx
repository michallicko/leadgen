import { useState, useRef, useCallback } from 'react'
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
// Challenge types
// ---------------------------------------------------------------------------

const CHALLENGE_TYPES = [
  {
    value: 'new_market_entry',
    label: 'New market entry',
    description: 'Entering a new vertical, geography, or segment',
  },
  {
    value: 'scaling_pipeline',
    label: 'Scaling pipeline',
    description: 'Growing outbound volume and conversion rates',
  },
  {
    value: 'reengaging_cold_leads',
    label: 'Re-engaging cold leads',
    description: 'Reviving stale contacts with fresh messaging',
  },
  {
    value: 'launching_new_product',
    label: 'Launching new product',
    description: 'Positioning and promoting a new offering',
  },
] as const

// ---------------------------------------------------------------------------
// Multi-domain tag input
// ---------------------------------------------------------------------------

function DomainTagInput({
  domains,
  onChange,
  disabled,
  placeholder,
}: {
  domains: string[]
  onChange: (domains: string[]) => void
  disabled: boolean
  placeholder?: string
}) {
  const [inputValue, setInputValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const addDomain = useCallback(
    (raw: string) => {
      const d = raw.trim().toLowerCase().replace(/^https?:\/\//, '').replace(/\/.*$/, '')
      if (d && !domains.includes(d)) {
        onChange([...domains, d])
      }
    },
    [domains, onChange],
  )

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',' || e.key === 'Tab') {
      e.preventDefault()
      if (inputValue.trim()) {
        addDomain(inputValue)
        setInputValue('')
      }
    } else if (e.key === 'Backspace' && !inputValue && domains.length > 0) {
      onChange(domains.slice(0, -1))
    }
  }

  const handleBlur = () => {
    if (inputValue.trim()) {
      addDomain(inputValue)
      setInputValue('')
    }
  }

  const removeDomain = (idx: number) => {
    onChange(domains.filter((_, i) => i !== idx))
  }

  return (
    <div
      className="flex flex-wrap items-center gap-1.5 w-full px-2 py-1.5 min-h-[38px] text-sm rounded-md border border-border-solid bg-surface-alt focus-within:ring-2 focus-within:ring-accent/40"
      onClick={() => inputRef.current?.focus()}
    >
      {domains.map((d, i) => (
        <span
          key={d}
          className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-accent/10 text-accent border border-accent/20"
        >
          {d}
          {!disabled && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                removeDomain(i)
              }}
              className="ml-0.5 text-accent/60 hover:text-accent transition-colors bg-transparent border-none cursor-pointer p-0 leading-none"
              aria-label={`Remove ${d}`}
            >
              &times;
            </button>
          )}
        </span>
      ))}
      <input
        ref={inputRef}
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        placeholder={domains.length === 0 ? (placeholder || 'yourcompany.com') : 'Add another...'}
        disabled={disabled}
        className="flex-1 min-w-[120px] bg-transparent text-text placeholder:text-text-dim focus:outline-none border-none p-0.5 disabled:opacity-50"
      />
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
  const { namespace } = useParams<{ namespace: string }>()
  const { tenant } = useTenantBySlug(namespace)

  const [description, setDescription] = useState('')
  const [challengeType, setChallengeType] = useState(CHALLENGE_TYPES[0].value)

  // Domain state: null means "user hasn't touched it yet" (show tenant default)
  const [userDomains, setUserDomains] = useState<string[] | null>(null)

  // Pre-fill from tenant config; user edits override
  const domains = userDomains ?? (tenant?.domain ? [tenant.domain] : [])
  const handleDomainsChange = useCallback((newDomains: string[]) => {
    setUserDomains(newDomains)
  }, [])

  const isValid = domains.length > 0 && description.trim().length > 0

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!isValid || isGenerating) return
    onGenerate({
      domains,
      description: description.trim(),
      challenge_type: challengeType,
    })
  }

  return (
    <div className="flex items-center justify-center h-full">
      <div className="w-full max-w-lg p-8 rounded-xl border border-border-solid bg-surface">
        <h2 className="text-xl font-semibold text-text mb-1">
          Generate Your GTM Strategy
        </h2>
        <p className="text-sm text-text-muted mb-6">
          Tell us about your company and the AI will research your market and
          draft a complete strategy playbook.
        </p>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Company description */}
          <div>
            <label
              htmlFor="pb-description"
              className="block text-sm font-medium text-text mb-1"
            >
              Company description
            </label>
            <textarea
              id="pb-description"
              required
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what your company does, who you serve, and what makes you different..."
              rows={3}
              disabled={isGenerating}
              className="w-full px-3 py-2 text-sm rounded-md border border-border-solid bg-surface-alt text-text placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-accent/40 resize-none disabled:opacity-50"
            />
          </div>

          {/* Challenge type */}
          <div>
            <label className="block text-sm font-medium text-text mb-2">
              Primary challenge
            </label>
            <div className="grid grid-cols-2 gap-2">
              {CHALLENGE_TYPES.map((ct) => {
                const selected = challengeType === ct.value
                return (
                  <button
                    key={ct.value}
                    type="button"
                    disabled={isGenerating}
                    onClick={() => setChallengeType(ct.value)}
                    className={`text-left px-3 py-2.5 rounded-md border transition-colors cursor-pointer disabled:opacity-50 ${
                      selected
                        ? 'border-accent bg-accent/10 text-text'
                        : 'border-border-solid bg-surface-alt text-text-muted hover:border-border hover:text-text'
                    }`}
                  >
                    <span className="block text-sm font-medium">{ct.label}</span>
                    <span className="block text-xs text-text-dim mt-0.5 leading-tight">
                      {ct.description}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Domains */}
          <div>
            <label
              htmlFor="pb-domains"
              className="block text-sm font-medium text-text mb-1"
            >
              Domains
              <span className="ml-1 text-text-dim font-normal">
                (your company + competitors)
              </span>
            </label>
            <DomainTagInput
              domains={domains}
              onChange={handleDomainsChange}
              disabled={isGenerating}
              placeholder="yourcompany.com"
            />
            <p className="text-xs text-text-dim mt-1">
              First domain is your company. Press Enter to add more (competitors, partners).
            </p>
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
