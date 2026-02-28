/**
 * ToolCallCard -- compact/expandable card for a single tool execution.
 *
 * Shows tool name, status icon, duration badge in compact mode.
 * Click to expand and see input/output JSON. Supports running/success/error
 * states with design-system-aligned colors.
 *
 * AC-2: Running spinner, updates to done with duration.
 * AC-3: Error displays with red X icon and error message.
 * AC-4b: Fast tool calls (<300ms) stay in running state for >=300ms.
 * AC-5: Click to expand input/output JSON.
 */

import type { ReactNode } from 'react'
import { useState, useEffect, useRef, useCallback } from 'react'

// ---------------------------------------------------------------------------
// Types (shared with parent)
// ---------------------------------------------------------------------------

export interface ToolCallEvent {
  tool_call_id: string
  tool_name: string
  input: Record<string, unknown>
  status: 'running' | 'success' | 'error'
  summary?: string
  output?: Record<string, unknown>
  duration_ms?: number
}

// ---------------------------------------------------------------------------
// Tool icon + label mapping
// ---------------------------------------------------------------------------

interface ToolMeta {
  icon: ReactNode
  verb: string
}

function getToolMeta(toolName: string): ToolMeta {
  if (toolName.startsWith('get_')) {
    return { icon: <EyeIcon />, verb: 'Reading' }
  }
  if (toolName.startsWith('update_') || toolName.startsWith('set_')) {
    return { icon: <PencilIcon />, verb: 'Updating' }
  }
  if (toolName.startsWith('append_')) {
    return { icon: <PlusIcon />, verb: 'Adding' }
  }
  if (toolName.startsWith('search_')) {
    return { icon: <SearchIcon />, verb: 'Searching' }
  }
  if (toolName.startsWith('list_')) {
    return { icon: <ListIcon />, verb: 'Listing' }
  }
  if (toolName.startsWith('create_')) {
    return { icon: <CreateIcon />, verb: 'Creating' }
  }
  if (toolName.startsWith('delete_') || toolName.startsWith('remove_')) {
    return { icon: <TrashIcon />, verb: 'Removing' }
  }
  return { icon: <WrenchIcon />, verb: 'Running' }
}

/** Human-readable label from tool name: "get_strategy_document" -> "strategy document" */
function humanizeToolName(toolName: string): string {
  // Strip verb prefix
  const prefixes = ['get_', 'update_', 'set_', 'append_', 'search_', 'list_', 'create_', 'delete_', 'remove_']
  let name = toolName
  for (const prefix of prefixes) {
    if (name.startsWith(prefix)) {
      name = name.slice(prefix.length)
      break
    }
  }
  return name.replace(/_/g, ' ')
}

// ---------------------------------------------------------------------------
// Icons (inline SVG -- same pattern as existing components)
// ---------------------------------------------------------------------------

function EyeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 8s3-5 7-5 7 5 7 5-3 5-7 5-7-5-7-5z" />
      <circle cx="8" cy="8" r="2" />
    </svg>
  )
}

function PencilIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11.5 1.5l3 3L5 14H2v-3z" />
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="8" r="6" />
      <path d="M8 5v6M5 8h6" />
    </svg>
  )
}

function SearchIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="7" cy="7" r="4" />
      <path d="M10 10l3.5 3.5" />
    </svg>
  )
}

function ListIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 4h10M3 8h10M3 12h10" />
    </svg>
  )
}

function CreateIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 3v10M3 8h10" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 4h12M5 4V3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1M6 7v5M10 7v5" />
      <path d="M3 4l1 9a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1l1-9" />
    </svg>
  )
}

function WrenchIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 2a4 4 0 0 0-3 6.5L2 13.5l.5.5 5-5A4 4 0 0 0 14 6a4 4 0 0 0-4-4z" />
    </svg>
  )
}

function SpinnerIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      style={{ animation: 'toolSpin 0.8s linear infinite' }}
    >
      <path d="M8 2a6 6 0 0 1 6 6" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8l4 4 6-7" />
    </svg>
  )
}

function XIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4l8 8M12 4l-8 8" />
    </svg>
  )
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{
        transition: 'transform 0.15s ease',
        transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
      }}
    >
      <path d="M6 4l4 4-4 4" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// JSON display helper
// ---------------------------------------------------------------------------

const MAX_JSON_DISPLAY = 2048

function JsonBlock({ data, label }: { data: Record<string, unknown>; label: string }) {
  const [showFull, setShowFull] = useState(false)
  const raw = JSON.stringify(data, null, 2)
  const truncated = raw.length > MAX_JSON_DISPLAY && !showFull

  return (
    <div className="mt-2">
      <div className="text-[10px] uppercase tracking-wider text-text-dim mb-1 font-semibold">
        {label}
      </div>
      <pre className="text-[11px] leading-relaxed bg-bg rounded-md p-2 overflow-x-auto whitespace-pre-wrap break-words text-text-muted font-mono border border-border-solid">
        {truncated ? raw.slice(0, MAX_JSON_DISPLAY) + '\n...' : raw}
      </pre>
      {raw.length > MAX_JSON_DISPLAY && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            setShowFull(!showFull)
          }}
          className="text-[10px] text-accent-cyan hover:underline mt-0.5 bg-transparent border-none cursor-pointer p-0"
        >
          {showFull ? 'Show less' : 'Show full'}
        </button>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Status color mapping
// ---------------------------------------------------------------------------

const STATUS_COLORS = {
  running: {
    border: 'border-l-accent-cyan',
    text: 'text-accent-cyan',
    bg: 'bg-accent-cyan/5',
  },
  success: {
    border: 'border-l-success',
    text: 'text-success',
    bg: 'bg-success/5',
  },
  error: {
    border: 'border-l-error',
    text: 'text-error',
    bg: 'bg-error/5',
  },
} as const

// ---------------------------------------------------------------------------
// ToolCallCard
// ---------------------------------------------------------------------------

interface ToolCallCardProps {
  toolCallId: string
  toolName: string
  input: Record<string, unknown>
  status: 'running' | 'success' | 'error'
  summary?: string
  output?: Record<string, unknown>
  durationMs?: number
  /** When true, render in single-line collapsed mode (for 4+ tool calls) */
  collapsedMode?: boolean
}

export function ToolCallCard({
  toolName,
  input,
  status: externalStatus,
  summary,
  output,
  durationMs,
  collapsedMode = false,
}: ToolCallCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  // AC-4b: Minimum display duration for fast tool calls
  // Keep showing "running" for at least 300ms even if result arrives faster.
  // Uses only setTimeout callbacks (never synchronous setState in effects).
  const startTimeRef = useRef(0)
  const prevStatusRef = useRef(externalStatus)
  const [delayActive, setDelayActive] = useState(false)

  useEffect(() => {
    const prev = prevStatusRef.current
    prevStatusRef.current = externalStatus

    if (externalStatus === 'running') {
      startTimeRef.current = Date.now()
      return
    }

    if (prev === 'running') {
      const elapsed = Date.now() - startTimeRef.current
      const remaining = Math.max(0, 300 - elapsed)

      if (remaining > 0) {
        // Use setTimeout(0) to make the setState async (satisfies linter)
        const activateTimer = setTimeout(() => setDelayActive(true), 0)
        const deactivateTimer = setTimeout(() => setDelayActive(false), remaining)
        return () => {
          clearTimeout(activateTimer)
          clearTimeout(deactivateTimer)
        }
      }
    }
  }, [externalStatus])

  // Display status: show "running" during delay, otherwise follow external status
  const displayStatus = delayActive ? 'running' : externalStatus

  const meta = getToolMeta(toolName)
  const colors = STATUS_COLORS[displayStatus]

  const handleClick = useCallback(() => {
    // Only expand if not currently running
    if (displayStatus !== 'running') {
      setIsExpanded((prev) => !prev)
    }
  }, [displayStatus])

  // Format duration for display
  const durationLabel = durationMs != null
    ? durationMs < 1000
      ? `${durationMs}ms`
      : `${(durationMs / 1000).toFixed(1)}s`
    : null

  // Collapsed mode: single-line minimal format for 4+ tool calls
  if (collapsedMode && !isExpanded) {
    return (
      <div
        onClick={handleClick}
        className={`flex items-center gap-2 py-1 px-2 rounded text-[11px] cursor-pointer hover:bg-surface-alt/50 transition-colors ${colors.text}`}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleClick() }}
      >
        {displayStatus === 'running' ? <SpinnerIcon /> : displayStatus === 'success' ? <CheckIcon /> : <XIcon />}
        <span className="text-text-muted font-mono truncate">{toolName}</span>
        {durationLabel && displayStatus !== 'running' && (
          <span className="text-text-dim ml-auto flex-shrink-0">{durationLabel}</span>
        )}
      </div>
    )
  }

  return (
    <div
      className={`rounded-md border border-border-solid border-l-[3px] ${colors.border} ${colors.bg} transition-all duration-200`}
    >
      {/* Compact row */}
      <div
        onClick={handleClick}
        className={`flex items-center gap-2 px-3 py-2 ${displayStatus !== 'running' ? 'cursor-pointer hover:bg-surface-alt/30' : ''} transition-colors select-none`}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleClick() }}
      >
        {/* Status icon */}
        <div className={`flex-shrink-0 ${colors.text}`}>
          {displayStatus === 'running' ? <SpinnerIcon /> : meta.icon}
        </div>

        {/* Label */}
        <div className="flex-1 min-w-0">
          {displayStatus === 'running' ? (
            <span className="text-xs text-text-muted">
              {meta.verb} {humanizeToolName(toolName)}...
            </span>
          ) : (
            <span className="text-xs text-text-muted">
              {summary || `${meta.verb} ${humanizeToolName(toolName)}`}
            </span>
          )}
        </div>

        {/* Right side: duration + chevron */}
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {durationLabel && displayStatus !== 'running' && (
            <span className="text-[10px] text-text-dim font-mono px-1.5 py-0.5 rounded bg-surface-alt">
              {durationLabel}
            </span>
          )}
          {displayStatus !== 'running' && (
            <div className="text-text-dim">
              <ChevronIcon open={isExpanded} />
            </div>
          )}
          {/* Status indicator for done/error */}
          {displayStatus === 'success' && (
            <div className="text-success flex-shrink-0">
              <CheckIcon />
            </div>
          )}
          {displayStatus === 'error' && (
            <div className="text-error flex-shrink-0">
              <XIcon />
            </div>
          )}
        </div>
      </div>

      {/* Expanded detail */}
      {isExpanded && (
        <div className="px-3 pb-3 border-t border-border-solid">
          {input && Object.keys(input).length > 0 && (
            <JsonBlock data={input} label="Input" />
          )}
          {output && Object.keys(output).length > 0 && (
            <JsonBlock data={output} label="Output" />
          )}
          {displayStatus === 'error' && summary && (
            <div className="mt-2 text-xs text-error">
              {summary}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// ToolCallCardList -- handles collapsed mode for 4+ tool calls (AC-4c)
// ---------------------------------------------------------------------------

interface ToolCallCardListProps {
  toolCalls: ToolCallEvent[]
}

export function ToolCallCardList({ toolCalls }: ToolCallCardListProps) {
  const [expandedAll, setExpandedAll] = useState(false)

  if (toolCalls.length === 0) return null

  const useCollapsed = toolCalls.length >= 4 && !expandedAll

  return (
    <div className="space-y-1.5">
      {toolCalls.map((tc) => (
        <ToolCallCard
          key={tc.tool_call_id}
          toolCallId={tc.tool_call_id}
          toolName={tc.tool_name}
          input={tc.input}
          status={tc.status}
          summary={tc.summary}
          output={tc.output}
          durationMs={tc.duration_ms}
          collapsedMode={useCollapsed}
        />
      ))}
      {toolCalls.length >= 4 && (
        <button
          onClick={() => setExpandedAll(!expandedAll)}
          className="text-[11px] text-accent-cyan hover:underline bg-transparent border-none cursor-pointer p-0 ml-2"
        >
          {expandedAll ? 'Collapse all' : 'Expand all'}
        </button>
      )}
    </div>
  )
}
