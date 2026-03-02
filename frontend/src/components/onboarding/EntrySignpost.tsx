/**
 * Entry Signpost — full-page welcome shown when a namespace has no data.
 * Presents three paths: Build a Strategy, Import Contacts, Browse Templates.
 * Path selection is persisted to tenant settings via the API.
 */

import { useNavigate, useParams } from 'react-router'
import { usePatchOnboardingSettings } from '../../hooks/useOnboarding'

interface PathCard {
  id: 'strategy' | 'import' | 'templates'
  title: string
  description: string
  icon: React.ReactNode
  route: string
}

const PATH_CARDS: PathCard[] = [
  {
    id: 'strategy',
    title: 'Build a Strategy',
    description:
      'Define your ideal customer profile and outreach strategy. The AI will help you draft a complete GTM playbook.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        className="w-8 h-8"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
        <path d="M8 7h8M8 11h6" />
      </svg>
    ),
    route: 'playbook',
  },
  {
    id: 'import',
    title: 'Import Contacts',
    description:
      'Already have a list of prospects? Upload a CSV or connect your CRM to get started right away.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        className="w-8 h-8"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M16 17l-4-4-4 4" />
        <path d="M12 13V21" />
        <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
      </svg>
    ),
    route: 'import',
  },
  {
    id: 'templates',
    title: 'Browse Templates',
    description:
      'Start from a proven GTM template. Pick an industry-specific strategy and customize it for your business.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        className="w-8 h-8"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
    route: 'playbook',
  },
]

export function EntrySignpost() {
  const { namespace } = useParams<{ namespace: string }>()
  const navigate = useNavigate()
  const patchSettings = usePatchOnboardingSettings()

  const handlePathSelect = (card: PathCard) => {
    // Persist the selection
    patchSettings.mutate(
      { onboarding_path: card.id },
      {
        onSuccess: () => {
          navigate(`/${namespace}/${card.route}`)
        },
        onError: () => {
          // Navigate anyway even if persistence fails
          navigate(`/${namespace}/${card.route}`)
        },
      },
    )
  }

  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-120px)]">
      <div className="w-full max-w-3xl px-6">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-accent/10 mb-4">
            <svg
              viewBox="0 0 24 24"
              className="w-7 h-7 text-accent"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <h1 className="text-2xl font-semibold text-text mb-2">
            Welcome to your workspace
          </h1>
          <p className="text-sm text-text-muted max-w-md mx-auto">
            Choose where you'd like to start. You can always come back and explore the other paths later.
          </p>
        </div>

        {/* Path cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {PATH_CARDS.map((card) => (
            <button
              key={card.id}
              onClick={() => handlePathSelect(card)}
              disabled={patchSettings.isPending}
              className="group flex flex-col items-start p-6 rounded-xl border border-border-solid bg-surface hover:border-accent/40 hover:bg-accent/5 transition-all text-left cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="text-text-muted group-hover:text-accent transition-colors mb-4">
                {card.icon}
              </div>
              <h3 className="text-sm font-semibold text-text mb-1.5">
                {card.title}
              </h3>
              <p className="text-xs text-text-muted leading-relaxed">
                {card.description}
              </p>
              <span className="mt-4 text-xs font-medium text-accent opacity-0 group-hover:opacity-100 transition-opacity">
                Get started &rarr;
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
