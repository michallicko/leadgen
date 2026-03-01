import { useCallback } from 'react'

/* ── Types ──────────────────────────────────────────────── */

export interface ChatFilterPayload {
  /** Unique ID so we can track which suggestion is pending */
  id: string
  /** Human-readable description of what the chat suggested */
  description: string
  /** Filter key-value pairs to apply */
  filters: Record<string, string | string[]>
  /** Timestamp for auto-dismiss */
  timestamp: number
}

interface ChatFilterSyncBarProps {
  pending: ChatFilterPayload | null
  onAccept: (filters: Record<string, string | string[]>) => void
  onDismiss: () => void
}

/* ── Component ──────────────────────────────────────────── */

export function ChatFilterSyncBar({ pending, onAccept, onDismiss }: ChatFilterSyncBarProps) {
  const handleAccept = useCallback(() => {
    if (!pending) return
    onAccept(pending.filters)
  }, [pending, onAccept])

  if (!pending) return null

  // Extract filter labels for display pills
  const filterPills = Object.entries(pending.filters).map(([key, value]) => {
    const displayVal = Array.isArray(value) ? value.join(', ') : value
    return { key, value: displayVal }
  })

  return (
    <div
      className="flex items-center gap-2 px-4 py-2 bg-accent/8 border border-accent/20 rounded-lg mb-3"
      role="alert"
      style={{ animation: 'chatFilterSlideIn 0.2s ease-out' }}
    >
      {/* Icon */}
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="text-accent flex-shrink-0">
        <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm-.5 3.5h1v4h-1v-4zm0 5h1v1h-1v-1z" fill="currentColor" />
      </svg>

      {/* Message */}
      <div className="flex-1 min-w-0 flex flex-wrap items-center gap-1.5 text-xs text-text">
        <span className="text-text-muted">Chat applied filters:</span>
        {filterPills.map((pill) => (
          <span
            key={pill.key}
            className="inline-flex items-center px-1.5 py-0.5 rounded bg-accent/15 text-accent text-[11px]"
          >
            {pill.key}: {pill.value}
          </span>
        ))}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <button
          type="button"
          onClick={handleAccept}
          className="px-2.5 py-1 text-[11px] font-medium rounded-md bg-accent text-white border-none cursor-pointer hover:bg-accent-hover transition-colors"
        >
          Apply
        </button>
        <button
          type="button"
          onClick={onDismiss}
          className="px-2.5 py-1 text-[11px] text-text-muted hover:text-text bg-transparent border border-border-solid rounded-md cursor-pointer transition-colors"
        >
          Dismiss
        </button>
      </div>

      <style>{`
        @keyframes chatFilterSlideIn {
          from { transform: translateY(-8px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      `}</style>
    </div>
  )
}
