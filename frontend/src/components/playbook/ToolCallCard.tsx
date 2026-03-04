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
import ReactMarkdown from 'react-markdown'

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
  /** Research events include a target (e.g., domain being researched) */
  target?: string
}

// ---------------------------------------------------------------------------
// Tool icon + label mapping
// ---------------------------------------------------------------------------

interface ToolMeta {
  icon: ReactNode
  verb: string
}

function getToolMeta(toolName: string): ToolMeta {
  // Research step tool names (from research_service.py)
  const lower = toolName.toLowerCase()
  if (lower.includes('website') || lower.includes('web research') || lower.includes('company website')) {
    return { icon: <GlobeIcon />, verb: 'Researching' }
  }
  if (lower.includes('web search') || lower.includes('web intelligence') || lower.includes('search')) {
    return { icon: <SearchIcon />, verb: 'Searching' }
  }
  if (lower.includes('analysis') || lower.includes('synthesis') || lower.includes('ai analysis')) {
    return { icon: <BrainIcon />, verb: 'Analyzing' }
  }
  if (lower.includes('database') || lower.includes('db_save') || lower.includes('save')) {
    return { icon: <CreateIcon />, verb: 'Saving' }
  }

  // Standard agent tool prefixes
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
  // Research tool names are already human-friendly (e.g., "Company Website Research")
  if (toolName.includes(' ')) return toolName

  // Strip verb prefix for agent tool names
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

function GlobeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="8" r="6" />
      <path d="M2 8h12M8 2c2 2 3 4 3 6s-1 4-3 6c-2-2-3-4-3-6s1-4 3-6z" />
    </svg>
  )
}

function BrainIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 14V8M8 8c0-3 2-5 4-5s2 2 2 3-1 2-2 2M8 8c0-3-2-5-4-5S2 5 2 6s1 2 2 2" />
      <path d="M6 10c-1 0-2 .5-2 1.5S5 13 6 13M10 10c1 0 2 .5 2 1.5s-1 1.5-2 1.5" />
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
// JSON display helper (fallback for raw view)
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
// Human-formatted detail renderer (BL-192)
// ---------------------------------------------------------------------------

/** Convert camelCase or snake_case to "Title Case" label */
function humanizeLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

/** Check if a value is "empty" (null, undefined, empty string, empty array/object) */
function isEmpty(value: unknown): boolean {
  if (value == null) return true
  if (typeof value === 'string' && value.trim() === '') return true
  if (Array.isArray(value) && value.length === 0) return true
  if (typeof value === 'object' && Object.keys(value as Record<string, unknown>).length === 0) return true
  return false
}

/** Render a single value as human-readable content */
function FormattedValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (isEmpty(value)) return null

  // Boolean
  if (typeof value === 'boolean') {
    return <span className="text-xs text-text-muted">{value ? 'Yes' : 'No'}</span>
  }

  // Number
  if (typeof value === 'number') {
    return <span className="text-xs text-text-muted font-mono">{value.toLocaleString()}</span>
  }

  // String — render as markdown if it contains formatting markers, otherwise plain text
  if (typeof value === 'string') {
    // Detect markdown: headers, bold/italic markers, links, lists, code blocks, tables
    const hasMarkdown = /[*_#\[\]`|>-]/.test(value) && value.length > 50
    if (hasMarkdown) {
      return (
        <div className="tool-card-markdown text-xs text-text-muted leading-relaxed">
          <ReactMarkdown>{value}</ReactMarkdown>
        </div>
      )
    }
    return <p className="text-xs text-text-muted leading-relaxed m-0">{value}</p>
  }

  // Array — render as bullet list or comma-separated for simple values
  if (Array.isArray(value)) {
    const allSimple = value.every((v) => typeof v === 'string' || typeof v === 'number')

    if (allSimple && value.length <= 5) {
      // Short list of simple values — render as pills/tags
      return (
        <div className="flex flex-wrap gap-1">
          {value.map((item, i) => (
            <span
              key={i}
              className="text-[11px] px-2 py-0.5 rounded-full bg-surface-alt text-text-muted border border-border-solid"
            >
              {String(item)}
            </span>
          ))}
        </div>
      )
    }

    // Longer list — bullet points
    return (
      <ul className="text-xs text-text-muted leading-relaxed m-0 pl-4 space-y-0.5 list-disc">
        {value.map((item, i) => (
          <li key={i}>
            {typeof item === 'object' && item !== null ? (
              <FormattedValue value={item} depth={depth + 1} />
            ) : (
              String(item)
            )}
          </li>
        ))}
      </ul>
    )
  }

  // Object — render as labeled sub-section
  if (typeof value === 'object' && value !== null) {
    const entries = Object.entries(value as Record<string, unknown>).filter(
      ([, v]) => !isEmpty(v),
    )
    if (entries.length === 0) return null

    return (
      <div className={`space-y-1.5 ${depth > 0 ? 'pl-3 border-l border-border-solid' : ''}`}>
        {entries.map(([k, v]) => (
          <div key={k}>
            <div className="text-[10px] uppercase tracking-wider text-text-dim font-semibold mb-0.5">
              {humanizeLabel(k)}
            </div>
            <FormattedValue value={v} depth={depth + 1} />
          </div>
        ))}
      </div>
    )
  }

  // Fallback
  return <span className="text-xs text-text-muted">{String(value)}</span>
}

function HumanFormattedDetail({
  data: rawData,
  label,
}: {
  data: Record<string, unknown>
  label: string
}) {
  const [showRaw, setShowRaw] = useState(false)

  // Defensive: if data is a JSON string (backend sends output as string),
  // parse it into an object. Prevents Object.entries() from enumerating
  // individual characters with numeric indices.
  let data = rawData
  if (typeof rawData === 'string') {
    try {
      const parsed = JSON.parse(rawData)
      if (typeof parsed === 'object' && parsed !== null) {
        data = parsed as Record<string, unknown>
      } else {
        // Primitive JSON value — wrap it for display
        data = { value: parsed }
      }
    } catch {
      // Not JSON — show the raw string
      data = { value: rawData }
    }
  }

  const entries = Object.entries(data).filter(([, v]) => !isEmpty(v))
  if (entries.length === 0) return null

  return (
    <div className="mt-2">
      <div className="text-[10px] uppercase tracking-wider text-text-dim mb-1.5 font-semibold">
        {label}
      </div>

      {showRaw ? (
        <JsonBlock data={data} label="" />
      ) : (
        <div className="space-y-2 bg-bg rounded-md p-2.5 border border-border-solid">
          {entries.map(([key, value]) => (
            <div key={key}>
              <div className="text-[10px] uppercase tracking-wider text-text-dim font-semibold mb-0.5">
                {humanizeLabel(key)}
              </div>
              <FormattedValue value={value} />
            </div>
          ))}
        </div>
      )}

      <button
        onClick={(e) => {
          e.stopPropagation()
          setShowRaw(!showRaw)
        }}
        className="text-[10px] text-text-dim hover:text-accent-cyan mt-1 bg-transparent border-none cursor-pointer p-0 transition-colors"
      >
        {showRaw ? 'Show formatted' : 'Show raw'}
      </button>
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
  /** Research events include a target (e.g., domain being researched) */
  target?: string
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
  target,
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
              {meta.verb} {humanizeToolName(toolName)}
              {target && <span className="text-text-dim ml-1">({target})</span>}
              ...
            </span>
          ) : (
            <span className="text-xs text-text-muted">
              {summary || `${meta.verb} ${humanizeToolName(toolName)}`}
              {target && !summary && <span className="text-text-dim ml-1">({target})</span>}
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
            <HumanFormattedDetail data={input} label="Input" />
          )}
          {output && Object.keys(output).length > 0 && (
            <HumanFormattedDetail data={output} label="Output" />
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
          target={tc.target}
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
