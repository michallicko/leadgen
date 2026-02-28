/**
 * ThinkingIndicator -- animated pulsing dots shown while the AI is processing.
 *
 * Appears inline in the message stream (same layout as StreamingBubble)
 * after the user sends a message. Disappears when the first `tool_start`
 * or `chunk` SSE event arrives.
 */

// ---------------------------------------------------------------------------
// Icons (duplicated from ChatMessages to keep this self-contained)
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
// ThinkingIndicator
// ---------------------------------------------------------------------------

export function ThinkingIndicator() {
  return (
    <div className="flex gap-3 flex-row">
      {/* Avatar — same as assistant messages */}
      <div className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5 bg-accent-cyan/15 text-accent-cyan">
        <AssistantIcon />
      </div>

      {/* Pulsing dots */}
      <div className="rounded-lg px-4 py-3 bg-surface-alt border border-border-solid flex items-center gap-1.5">
        <span
          className="w-2 h-2 rounded-full bg-accent-cyan"
          style={{ animation: 'thinkPulse 1.4s ease-in-out infinite' }}
        />
        <span
          className="w-2 h-2 rounded-full bg-accent-cyan"
          style={{ animation: 'thinkPulse 1.4s ease-in-out 0.2s infinite' }}
        />
        <span
          className="w-2 h-2 rounded-full bg-accent-cyan"
          style={{ animation: 'thinkPulse 1.4s ease-in-out 0.4s infinite' }}
        />
      </div>
    </div>
  )
}
