/**
 * ThinkingHistory — collapsible history of agent research findings.
 *
 * Shown below an agent's response message after it completes.
 * Displays a toggle to expand/collapse the chronological list of
 * all findings from that agent turn.
 *
 * BL-1015: Transparent Thinking UX
 */

import { useState } from 'react'
import type { ThinkingFinding } from './ThinkingStatus'

interface ThinkingHistoryProps {
  findings: ThinkingFinding[]
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function ChevronIcon({ isExpanded }: { isExpanded: boolean }) {
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
      className={`transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
    >
      <path d="M3 4.5l3 3 3-3" />
    </svg>
  )
}

function SearchIcon() {
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
      <circle cx="5.5" cy="5.5" r="3.5" />
      <path d="M8 8l2.5 2.5" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Time formatter
// ---------------------------------------------------------------------------

function formatTimestamp(ts: number): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return ''
  }
}

// ---------------------------------------------------------------------------
// ThinkingHistory
// ---------------------------------------------------------------------------

export function ThinkingHistory({ findings }: ThinkingHistoryProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  if (findings.length === 0) return null

  return (
    <div className="ml-10 mt-1">
      {/* Toggle button */}
      <button
        onClick={() => setIsExpanded((prev) => !prev)}
        className="flex items-center gap-1.5 text-[11px] text-text-dim hover:text-text-muted transition-colors bg-transparent border-none cursor-pointer px-0 py-0.5"
      >
        <SearchIcon />
        <span>
          {isExpanded ? 'Hide' : 'Show'} thinking ({findings.length} step{findings.length !== 1 ? 's' : ''})
        </span>
        <ChevronIcon isExpanded={isExpanded} />
      </button>

      {/* Expanded findings list */}
      {isExpanded && (
        <div className="mt-1.5 space-y-1 border-l-2 border-border-solid pl-3">
          {findings.map((f, idx) => (
            <div key={idx} className="text-[11px] leading-relaxed">
              <span className="text-text-dim font-mono">{formatTimestamp(f.timestamp)}</span>
              <span className="text-text-muted ml-1.5 font-medium">{f.action}</span>
              {f.finding && (
                <span className="text-text-dim ml-1">{f.finding}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
