/**
 * ThinkingStatus — live status bubble shown during agent work.
 *
 * Displays the latest research finding (action + finding text) with
 * an animated pulse indicator. Only shows the most recent finding —
 * previous ones are hidden (available via ThinkingHistory after completion).
 *
 * BL-1015: Transparent Thinking UX
 */

// ---------------------------------------------------------------------------
// Types (exported for reuse in ChatProvider / ThinkingHistory)
// ---------------------------------------------------------------------------

export interface ThinkingFinding {
  action: string      // e.g. "Reading unitedarts.cz"
  finding: string     // e.g. "Found: event production company, Prague-based"
  timestamp: number
  step?: number
}

interface ThinkingStatusProps {
  currentFinding: ThinkingFinding | null
  isActive: boolean
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function AssistantIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="2" y="3" width="12" height="10" rx="2" />
      <circle cx="6" cy="8" r="1" fill="currentColor" stroke="none" />
      <circle cx="10" cy="8" r="1" fill="currentColor" stroke="none" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// ThinkingStatus
// ---------------------------------------------------------------------------

export function ThinkingStatus({ currentFinding, isActive }: ThinkingStatusProps) {
  if (!isActive) return null

  return (
    <div className="flex gap-3 flex-row">
      {/* Avatar */}
      <div className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5 bg-accent-cyan/15 text-accent-cyan">
        <AssistantIcon />
      </div>

      {/* Status bubble */}
      <div className="max-w-[80%] rounded-lg px-4 py-2.5 bg-surface-alt border border-border-solid">
        <div className="flex items-center gap-2">
          {/* Animated pulse indicator */}
          <span
            className="flex-shrink-0 w-2 h-2 rounded-full bg-accent-cyan"
            style={{ animation: 'thinkPulse 1.4s ease-in-out infinite' }}
          />

          {currentFinding ? (
            <p className="text-xs text-text-muted leading-relaxed">
              <span className="text-text font-medium">{currentFinding.action}</span>
              {currentFinding.finding && (
                <>
                  {' '}
                  <span className="text-text-dim">&mdash;</span>{' '}
                  <span className="text-text-dim">{currentFinding.finding}</span>
                </>
              )}
            </p>
          ) : (
            <div className="flex items-center gap-1.5">
              <span
                className="w-1.5 h-1.5 rounded-full bg-accent-cyan"
                style={{ animation: 'thinkPulse 1.4s ease-in-out infinite' }}
              />
              <span
                className="w-1.5 h-1.5 rounded-full bg-accent-cyan"
                style={{ animation: 'thinkPulse 1.4s ease-in-out 0.2s infinite' }}
              />
              <span
                className="w-1.5 h-1.5 rounded-full bg-accent-cyan"
                style={{ animation: 'thinkPulse 1.4s ease-in-out 0.4s infinite' }}
              />
              <span className="text-xs text-text-dim ml-1">Thinking...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
