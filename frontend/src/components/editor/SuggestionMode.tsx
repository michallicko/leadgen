/**
 * SuggestionMode — accept/reject changes UI for agent edits.
 *
 * Shows a banner with batch accept/reject controls when agent edits
 * are pending. Individual suggestions can be accepted or rejected
 * from within the document (via the suggestion list).
 *
 * Works with the useAgentEditing hook which tracks pending edits.
 */

import { useCallback } from 'react'
import type { Suggestion } from '../../types/agui'

// ---------------------------------------------------------------------------
// SuggestionBanner — top-of-editor batch controls
// ---------------------------------------------------------------------------

interface SuggestionBannerProps {
  /** Number of pending suggestions. */
  count: number
  /** Accept all pending suggestions. */
  onAcceptAll: () => void
  /** Reject all pending suggestions. */
  onRejectAll: () => void
}

export function SuggestionBanner({ count, onAcceptAll, onRejectAll }: SuggestionBannerProps) {
  if (count === 0) return null

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-accent/10 border-b border-accent/20">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
        <span className="text-sm text-text">
          {count} pending {count === 1 ? 'suggestion' : 'suggestions'} from AI
        </span>
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onRejectAll}
          className="px-3 py-1 text-xs font-medium rounded border border-border-solid
                     text-text-muted hover:text-red-600 hover:border-red-300
                     transition-colors"
        >
          Reject All
        </button>
        <button
          type="button"
          onClick={onAcceptAll}
          className="px-3 py-1 text-xs font-medium rounded
                     bg-accent text-white hover:bg-accent-hover
                     transition-colors"
        >
          Accept All
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// SuggestionItem — individual suggestion with accept/reject
// ---------------------------------------------------------------------------

interface SuggestionItemProps {
  suggestion: Suggestion
  onAccept: (id: string) => void
  onReject: (id: string) => void
}

function SuggestionItem({ suggestion, onAccept, onReject }: SuggestionItemProps) {
  const typeStyles = {
    add: {
      label: 'Added',
      bg: 'bg-green-50 dark:bg-green-900/20',
      border: 'border-green-200 dark:border-green-800',
      badge: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
    },
    delete: {
      label: 'Deleted',
      bg: 'bg-red-50 dark:bg-red-900/20',
      border: 'border-red-200 dark:border-red-800',
      badge: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
    },
    replace: {
      label: 'Replaced',
      bg: 'bg-blue-50 dark:bg-blue-900/20',
      border: 'border-blue-200 dark:border-blue-800',
      badge: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
    },
  }

  const style = typeStyles[suggestion.type]

  return (
    <div className={`rounded-md border ${style.border} ${style.bg} p-3 space-y-2`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${style.badge}`}>
            {style.label}
          </span>
          <span className="text-xs text-text-muted">in {suggestion.section}</span>
        </div>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={() => onReject(suggestion.id)}
            className="p-1 text-xs text-text-muted hover:text-red-600 transition-colors"
            title="Reject this change"
          >
            Reject
          </button>
          <button
            type="button"
            onClick={() => onAccept(suggestion.id)}
            className="p-1 text-xs text-accent hover:text-accent-hover transition-colors"
            title="Accept this change"
          >
            Accept
          </button>
        </div>
      </div>

      {/* Diff preview */}
      <div className="text-xs font-mono space-y-1">
        {suggestion.originalContent && (
          <div className="line-through text-red-500/70 bg-red-50 dark:bg-red-900/10 px-2 py-1 rounded">
            {truncatePreview(suggestion.originalContent)}
          </div>
        )}
        {suggestion.type !== 'delete' && (
          <div className="text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/10 px-2 py-1 rounded">
            {truncatePreview(suggestion.content)}
          </div>
        )}
      </div>
    </div>
  )
}

/** Truncate preview text to a reasonable length. */
function truncatePreview(text: string, maxLen: number = 200): string {
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen) + '...'
}

// ---------------------------------------------------------------------------
// SuggestionList — scrollable list of all pending suggestions
// ---------------------------------------------------------------------------

interface SuggestionListProps {
  suggestions: Suggestion[]
  onAccept: (id: string) => void
  onReject: (id: string) => void
  onAcceptAll: () => void
  onRejectAll: () => void
}

export function SuggestionList({
  suggestions,
  onAccept,
  onReject,
  onAcceptAll,
  onRejectAll,
}: SuggestionListProps) {
  if (suggestions.length === 0) return null

  return (
    <div className="space-y-2 p-3 border-t border-border-solid bg-surface">
      <SuggestionBanner
        count={suggestions.length}
        onAcceptAll={onAcceptAll}
        onRejectAll={onRejectAll}
      />
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {suggestions.map((s) => (
          <SuggestionItem
            key={s.id}
            suggestion={s}
            onAccept={onAccept}
            onReject={onReject}
          />
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// useSuggestions hook — manages suggestion accept/reject logic
// ---------------------------------------------------------------------------

interface UseSuggestionsReturn {
  /** Accept a single suggestion by ID. */
  acceptSuggestion: (id: string) => void
  /** Reject a single suggestion by ID. */
  rejectSuggestion: (id: string) => void
  /** Accept all pending suggestions. */
  acceptAll: () => void
  /** Reject all pending suggestions. */
  rejectAll: () => void
}

export function useSuggestions(
  suggestions: Suggestion[],
  onClearSuggestion: (id: string) => void,
  onClearAll: () => void,
  editor: { commands: { undo: () => boolean } } | null,
): UseSuggestionsReturn {
  const acceptSuggestion = useCallback(
    (id: string) => {
      // Accept = keep the change as-is, just remove from pending list
      onClearSuggestion(id)
    },
    [onClearSuggestion],
  )

  const rejectSuggestion = useCallback(
    (id: string) => {
      // Reject = undo the change
      // For simplicity, we use editor undo which reverts the last operation.
      // In a production system, this would use tracked transactions.
      if (editor) {
        editor.commands.undo()
      }
      onClearSuggestion(id)
    },
    [editor, onClearSuggestion],
  )

  const acceptAll = useCallback(() => {
    // Accept all = clear pending list, keep all changes
    onClearAll()
  }, [onClearAll])

  const rejectAll = useCallback(() => {
    // Reject all = undo all pending changes
    if (editor) {
      for (let i = 0; i < suggestions.length; i++) {
        editor.commands.undo()
      }
    }
    onClearAll()
  }, [editor, suggestions.length, onClearAll])

  return { acceptSuggestion, rejectSuggestion, acceptAll, rejectAll }
}
