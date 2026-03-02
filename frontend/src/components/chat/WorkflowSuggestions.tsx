/**
 * WorkflowSuggestions — proactive next-step cards shown in the chat panel.
 *
 * Displays contextual suggestions based on the namespace's workflow state.
 * Each suggestion has an icon, summary, detail text, and an action button
 * that navigates to the relevant page.
 *
 * BL-135: Proactive Next-Step Suggestions
 */

import { useNavigate, useParams } from 'react-router'
import { useWorkflowSuggestions } from '../../hooks/useWorkflowSuggestions'

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function StrategyIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 2L11 7H16L12 10.5L13.5 16L9 12.5L4.5 16L6 10.5L2 7H7L9 2Z" />
    </svg>
  )
}

function ContactsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="6" r="3" />
      <path d="M3 16c0-3 2.69-5 6-5s6 2 6 5" />
    </svg>
  )
}

function EnrichIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="9" r="7" />
      <path d="M9 5v4l3 2" />
    </svg>
  )
}

function CampaignIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3h12v12H3z" />
      <path d="M7 7l2 2 4-4" />
    </svg>
  )
}

function MessagesIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 11a2 2 0 0 1-2 2H7l-4 3V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function ArrowRightIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 3l4 4-4 4" />
    </svg>
  )
}

const ICON_MAP: Record<string, React.FC> = {
  strategy: StrategyIcon,
  contacts: ContactsIcon,
  enrich: EnrichIcon,
  campaign: CampaignIcon,
  messages: MessagesIcon,
}

const ICON_COLORS: Record<string, string> = {
  strategy: 'bg-accent/15 text-accent-hover',
  contacts: 'bg-accent-cyan/15 text-accent-cyan',
  enrich: 'bg-emerald-500/15 text-emerald-400',
  campaign: 'bg-amber-500/15 text-amber-400',
  messages: 'bg-violet-500/15 text-violet-400',
}

// ---------------------------------------------------------------------------
// SuggestionCard
// ---------------------------------------------------------------------------

interface SuggestionCardProps {
  icon: string
  summary: string
  detail: string
  actionLabel: string
  onAction: () => void
  onDismiss: () => void
}

function SuggestionCard({
  icon,
  summary,
  detail,
  actionLabel,
  onAction,
  onDismiss,
}: SuggestionCardProps) {
  const IconComponent = ICON_MAP[icon] || StrategyIcon
  const iconColor = ICON_COLORS[icon] || ICON_COLORS.strategy

  return (
    <div className="bg-surface-alt border border-border-solid rounded-lg p-3 space-y-2">
      <div className="flex items-start gap-2.5">
        <div
          className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${iconColor}`}
        >
          <IconComponent />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-text leading-snug">{summary}</p>
          <p className="text-xs text-text-muted mt-0.5 leading-relaxed">{detail}</p>
        </div>
        <button
          onClick={onDismiss}
          className="flex-shrink-0 w-5 h-5 flex items-center justify-center text-text-dim hover:text-text-muted transition-colors bg-transparent border-none cursor-pointer"
          aria-label="Dismiss suggestion"
          title="Dismiss"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <path d="M2 2l6 6M8 2l-6 6" />
          </svg>
        </button>
      </div>
      <button
        onClick={onAction}
        className="flex items-center gap-1.5 text-xs font-medium text-accent-hover hover:text-accent transition-colors bg-transparent border-none cursor-pointer px-0"
      >
        {actionLabel}
        <ArrowRightIcon />
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// WorkflowSuggestions
// ---------------------------------------------------------------------------

export function WorkflowSuggestions() {
  const { namespace } = useParams<{ namespace: string }>()
  const navigate = useNavigate()
  const { data: suggestions, isLoading } = useWorkflowSuggestions()

  // Track dismissed suggestions per session
  const dismissedKey = 'workflow_suggestions_dismissed'
  const getDismissed = (): string[] => {
    try {
      const stored = sessionStorage.getItem(dismissedKey)
      return stored ? JSON.parse(stored) : []
    } catch {
      return []
    }
  }

  const dismiss = (id: string) => {
    try {
      const current = getDismissed()
      current.push(id)
      sessionStorage.setItem(dismissedKey, JSON.stringify(current))
    } catch {
      // sessionStorage unavailable
    }
    // Force re-render by using a state-like approach (hack with DOM)
    // Actually, since we read from sessionStorage every render, just trigger one
    window.dispatchEvent(new Event('storage'))
  }

  if (isLoading || !suggestions || suggestions.length === 0) return null

  const dismissed = getDismissed()
  const visible = suggestions.filter((s) => !dismissed.includes(s.id))

  if (visible.length === 0) return null

  // Show at most 2 suggestions to avoid overwhelming
  const shown = visible.slice(0, 2)

  return (
    <div className="space-y-2 mb-3">
      <p className="text-[11px] font-medium text-text-dim uppercase tracking-wide px-0.5">
        Suggested next steps
      </p>
      {shown.map((suggestion) => (
        <SuggestionCard
          key={suggestion.id}
          icon={suggestion.icon}
          summary={suggestion.summary}
          detail={suggestion.detail}
          actionLabel={suggestion.action_label}
          onAction={() => {
            if (namespace) {
              navigate(`/${namespace}${suggestion.action_path}`)
            }
          }}
          onDismiss={() => dismiss(suggestion.id)}
        />
      ))}
    </div>
  )
}
