/**
 * Progress Checklist — lightweight onboarding progress widget.
 * Shows auto-completing milestones: strategy saved, contacts imported, campaign created.
 * Dismissible and persisted to tenant settings.
 */

import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import type { OnboardingStatus } from '../../hooks/useOnboarding'
import { usePatchOnboardingSettings } from '../../hooks/useOnboarding'

interface ProgressChecklistProps {
  status: OnboardingStatus
}

interface Milestone {
  key: string
  label: string
  route: string
  check: (s: OnboardingStatus) => boolean
}

const MILESTONES: Milestone[] = [
  {
    key: 'strategy',
    label: 'Save a strategy',
    route: 'playbook',
    check: (s) => s.has_strategy,
  },
  {
    key: 'contacts',
    label: 'Import contacts',
    route: 'import',
    check: (s) => s.contact_count > 0,
  },
  {
    key: 'campaign',
    label: 'Create a campaign',
    route: 'campaigns',
    check: (s) => s.campaign_count > 0,
  },
]

export function ProgressChecklist({ status }: ProgressChecklistProps) {
  const { namespace } = useParams<{ namespace: string }>()
  const navigate = useNavigate()
  const patchSettings = usePatchOnboardingSettings()
  const [dismissing, setDismissing] = useState(false)

  const completedCount = MILESTONES.filter((m) => m.check(status)).length
  const totalCount = MILESTONES.length
  const progressPct = Math.round((completedCount / totalCount) * 100)

  const handleDismiss = () => {
    setDismissing(true)
    patchSettings.mutate({ checklist_dismissed: true })
  }

  if (dismissing) return null

  return (
    <div className="mb-4 p-4 rounded-xl border border-border-solid bg-surface">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <svg
            viewBox="0 0 24 24"
            className="w-4 h-4 text-accent"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
          <span className="text-xs font-semibold text-text">Getting Started</span>
          <span className="text-[10px] text-text-muted">
            {completedCount}/{totalCount}
          </span>
        </div>
        <button
          onClick={handleDismiss}
          className="text-text-dim hover:text-text-muted text-xs bg-transparent border-none cursor-pointer p-0.5"
          aria-label="Dismiss checklist"
          title="Dismiss"
        >
          <svg
            viewBox="0 0 24 24"
            className="w-3.5 h-3.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Progress bar */}
      <div className="h-1 rounded-full bg-border mb-3 overflow-hidden">
        <div
          className="h-full rounded-full bg-accent transition-all duration-500"
          style={{ width: `${progressPct}%` }}
        />
      </div>

      {/* Milestones */}
      <ul className="space-y-1.5">
        {MILESTONES.map((m) => {
          const done = m.check(status)
          return (
            <li key={m.key}>
              <button
                onClick={() => !done && navigate(`/${namespace}/${m.route}`)}
                disabled={done}
                className={`flex items-center gap-2 w-full text-left text-xs rounded-md px-2 py-1.5 transition-colors bg-transparent border-none ${
                  done
                    ? 'text-text-dim cursor-default'
                    : 'text-text-muted hover:text-text hover:bg-surface-alt cursor-pointer'
                }`}
              >
                {/* Checkbox icon */}
                {done ? (
                  <svg
                    viewBox="0 0 24 24"
                    className="w-4 h-4 text-success flex-shrink-0"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                    <path d="M22 4L12 14.01l-3-3" />
                  </svg>
                ) : (
                  <div className="w-4 h-4 rounded-full border border-border-solid flex-shrink-0" />
                )}
                <span className={done ? 'line-through' : ''}>{m.label}</span>
                {!done && (
                  <svg
                    viewBox="0 0 24 24"
                    className="w-3 h-3 ml-auto opacity-0 group-hover:opacity-100 text-text-dim"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M9 18l6-6-6-6" />
                  </svg>
                )}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
