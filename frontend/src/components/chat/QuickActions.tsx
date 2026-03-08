/**
 * QuickActions — action buttons shown after an agent response.
 *
 * Two action types:
 * - chat_action: sends the label as a new chat message
 * - navigate: navigates to a target path (prepends namespace)
 *
 * BL-1017: Quick Actions
 */

// ---------------------------------------------------------------------------
// Types (exported for reuse)
// ---------------------------------------------------------------------------

export interface QuickAction {
  label: string
  action: string         // e.g. "score", "navigate", "new_thread"
  type: 'chat_action' | 'navigate'
  target?: string        // for navigate type: relative path e.g. "/contacts"
}

interface QuickActionsProps {
  actions: QuickAction[]
  onAction: (action: QuickAction) => void
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function ArrowRightIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4.5 2.5l4 3.5-4 3.5" />
    </svg>
  )
}

function ChatActionIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M11 7.5a1.5 1.5 0 0 1-1.5 1.5H4L1.5 11V3A1.5 1.5 0 0 1 3 1.5h6.5A1.5 1.5 0 0 1 11 3z" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// QuickActions
// ---------------------------------------------------------------------------

export function QuickActions({ actions, onAction }: QuickActionsProps) {
  if (actions.length === 0) return null

  return (
    <div className="ml-10 mt-2 flex flex-wrap gap-2">
      {actions.map((action, idx) => (
        <button
          key={idx}
          onClick={() => onAction(action)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-accent/30 text-accent-hover hover:bg-accent/10 hover:border-accent/50 transition-colors bg-transparent cursor-pointer"
        >
          {action.type === 'navigate' ? <ArrowRightIcon /> : <ChatActionIcon />}
          {action.label}
        </button>
      ))}
    </div>
  )
}
