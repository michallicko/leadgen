/**
 * Shared chat message list component — used by both inline PlaybookChat
 * and the global sliding ChatPanel.
 *
 * Contains: MessageBubble, StreamingBubble, EmptyState, ChatSkeleton.
 *
 * THINK feature: MessageBubble renders ToolCallCards above the
 * message text when message.extra.tool_calls is present (AC-6).
 * In-flight tool calls and thinking indicator are rendered between
 * persisted messages and the streaming bubble.
 */

import { useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'
import { ToolCallCardList, type ToolCallEvent } from '../playbook/ToolCallCard'
// ThinkingIndicator replaced by inline unified working state block
import { ChatMermaidBlock } from './ChatMermaidBlock'
import { WorkflowSuggestions } from './WorkflowSuggestions'
import { ThinkingStatus, type ThinkingFinding } from './ThinkingStatus'
import { ThinkingHistory } from './ThinkingHistory'
import { QuickActions, type QuickAction } from './QuickActions'

// ---------------------------------------------------------------------------
// Markdown components (mermaid code block rendering)
// ---------------------------------------------------------------------------

const markdownComponents: Components = {
  code({ className, children, ...props }) {
    // Detect fenced code blocks with ```mermaid via class name
    const langMatch = className ? /language-(\w+)/.exec(className) : null
    const lang = langMatch?.[1]

    if (lang === 'mermaid') {
      const code = String(children).replace(/\n$/, '')
      return <ChatMermaidBlock code={code} />
    }

    // For other fenced code blocks, render with syntax styling
    if (className) {
      return (
        <code className={`${className} block bg-surface-alt rounded p-2 text-xs font-mono overflow-x-auto`} {...props}>
          {children}
        </code>
      )
    }

    // Inline code
    return (
      <code className="bg-surface-alt px-1.5 py-0.5 rounded text-xs font-mono" {...props}>
        {children}
      </code>
    )
  },
  pre({ children }) {
    // Let the code component handle rendering — pre is just a pass-through
    return <>{children}</>
  },
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  extra?: Record<string, unknown>
  created_at: string
  page_context?: string | null
  thread_start?: boolean
}

interface ChatMessagesProps {
  messages: ChatMessage[]
  isStreaming: boolean
  streamingText: string
  isLoading?: boolean
  /** THINK: in-flight tool calls from the current agent turn */
  toolCalls?: ToolCallEvent[]
  /** THINK: show thinking indicator before first tool_start or chunk */
  isThinking?: boolean
  /** Dynamic status text for the thinking indicator */
  thinkingStatus?: string
  /** BL-1015: Current research finding during agent work */
  currentFinding?: ThinkingFinding | null
  /** BL-1015: Per-message thinking history, keyed by message ID */
  messageFindings?: Record<string, ThinkingFinding[]>
  /** BL-1017: Per-message quick actions, keyed by message ID */
  messageQuickActions?: Record<string, QuickAction[]>
  /** BL-1017: Handler for quick action button clicks */
  onQuickAction?: (action: QuickAction) => void
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function UserIcon() {
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
      <circle cx="8" cy="5" r="3" />
      <path d="M2 14c0-2.76 2.69-5 6-5s6 2.24 6 5" />
    </svg>
  )
}

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
// Time formatter
// ---------------------------------------------------------------------------

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}

// ---------------------------------------------------------------------------
// Extract persisted tool calls from message extra/metadata (AC-6)
// ---------------------------------------------------------------------------

/**
 * Map status from backend format to ToolCallEvent status.
 * Research events use "completed"/"running"/"error"; agent events use "success"/"error".
 */
function normalizeStatus(rawStatus: string): 'running' | 'success' | 'error' {
  if (rawStatus === 'error') return 'error'
  if (rawStatus === 'running') return 'running'
  return 'success' // "completed" or "success" both map to "success"
}

/** Safely coerce a value to Record<string, unknown>, parsing JSON strings. */
function toRecordOrUndefined(val: unknown): Record<string, unknown> | undefined {
  if (val == null) return undefined
  if (typeof val === 'object' && !Array.isArray(val)) return val as Record<string, unknown>
  if (typeof val === 'string' && val) {
    try {
      const parsed = JSON.parse(val)
      if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>
      }
    } catch {
      // not valid JSON
    }
  }
  return undefined
}

function getPersistedToolCalls(message: ChatMessage): ToolCallEvent[] | null {
  const extra = message.extra
  if (!extra || !Array.isArray(extra.tool_calls) || extra.tool_calls.length === 0) {
    return null
  }

  return (extra.tool_calls as Array<Record<string, unknown>>).map((tc, idx) => ({
    tool_call_id: (tc.tool_call_id as string) || (tc.id as string) || `persisted-${idx}`,
    tool_name: (tc.tool_name as string) || (tc.name as string) || 'unknown',
    input: (tc.input_args as Record<string, unknown>) || (tc.input as Record<string, unknown>) || {},
    status: normalizeStatus((tc.status as string) || 'success'),
    summary: (tc.summary as string) || undefined,
    // Research events store structured results in "detail"; agent events use "output_data"/"output"
    // Safely parse string values that may be JSON-encoded (defensive against mistyped data)
    output: toRecordOrUndefined(tc.output_data)
      || toRecordOrUndefined(tc.output)
      || toRecordOrUndefined(tc.detail)
      || undefined,
    duration_ms: (tc.duration_ms as number) || undefined,
    // Research events include target (e.g., domain being researched)
    target: (tc.target as string) || undefined,
  }))
}

/** Check if this message is a research progress message (should show tool cards only, no text bubble) */
function isResearchProgressMessage(message: ChatMessage): boolean {
  return !!message.extra?.is_research_progress
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

interface MessageBubbleProps {
  message: ChatMessage
  findings?: ThinkingFinding[]
  quickActions?: QuickAction[]
  onQuickAction?: (action: QuickAction) => void
}

function MessageBubble({ message, findings, quickActions, onQuickAction }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  // Don't render system messages (thread boundaries)
  if (message.role === 'system') return null

  // BL-208: Hidden messages (e.g. onboarding trigger prompts) show a
  // condensed placeholder instead of the full internal instructions.
  // Fallback: also detect by content prefix for messages saved before the
  // hidden flag was deployed to the backend.
  const isHidden =
    message.extra?.hidden ||
    (isUser && message.content.startsWith('Generate a complete GTM strategy'))
  if (isHidden) {
    return (
      <div className="flex gap-3 flex-row-reverse">
        <div className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5 bg-accent/20 text-accent-hover">
          <UserIcon />
        </div>
        <div className="text-xs text-text-muted italic py-2">
          Strategy generation started...
        </div>
      </div>
    )
  }

  // AC-6: Render persisted tool calls from message metadata
  const persistedToolCalls = !isUser ? getPersistedToolCalls(message) : null

  // Research progress messages show only tool cards -- no text bubble
  // (the summary is already displayed inside the tool card)
  const isResearchProgress = !isUser && isResearchProgressMessage(message)

  if (isResearchProgress && persistedToolCalls) {
    return (
      <div className="flex gap-3 flex-row">
        {/* Avatar */}
        <div className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5 bg-accent-cyan/15 text-accent-cyan">
          <AssistantIcon />
        </div>
        {/* Tool cards only -- no text bubble */}
        <div className="max-w-[80%]">
          <ToolCallCardList toolCalls={persistedToolCalls} />
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        {/* Avatar */}
        <div
          className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5 ${
            isUser
              ? 'bg-accent/20 text-accent-hover'
              : 'bg-accent-cyan/15 text-accent-cyan'
          }`}
        >
          {isUser ? <UserIcon /> : <AssistantIcon />}
        </div>

        {/* Content */}
        <div className="max-w-[80%] flex flex-col gap-1.5">
          {/* Tool call cards (above the text, for assistant messages) */}
          {persistedToolCalls && (
            <div className="mb-1">
              <ToolCallCardList toolCalls={persistedToolCalls} />
            </div>
          )}

          {/* Text bubble */}
          <div
            className={`rounded-lg px-4 py-2.5 text-sm leading-relaxed ${
              isUser
                ? 'bg-accent/15 text-text border border-accent/20'
                : 'bg-surface-alt text-text border border-border-solid'
            }`}
          >
            {isUser ? (
              <div className="whitespace-pre-wrap break-words">{message.content}</div>
            ) : (
              <div className="chat-markdown break-words">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
            <div
              className={`text-[11px] mt-1.5 ${
                isUser ? 'text-accent-hover/60 text-right' : 'text-text-dim'
              }`}
            >
              {formatTime(message.created_at)}
            </div>
          </div>
        </div>
      </div>

      {/* BL-1015: Thinking history toggle (below assistant messages) */}
      {!isUser && findings && findings.length > 0 && (
        <ThinkingHistory findings={findings} />
      )}

      {/* BL-1017: Quick action buttons (below assistant messages) */}
      {!isUser && quickActions && quickActions.length > 0 && onQuickAction && (
        <QuickActions actions={quickActions} onAction={onQuickAction} />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Streaming indicator
// ---------------------------------------------------------------------------

function StreamingBubble({ text }: { text: string }) {
  return (
    <div className="flex gap-3 flex-row">
      {/* Avatar */}
      <div className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5 bg-accent-cyan/15 text-accent-cyan">
        <AssistantIcon />
      </div>

      {/* Content */}
      <div className="max-w-[80%] rounded-lg px-4 py-2.5 text-sm leading-relaxed bg-surface-alt text-text border border-border-solid">
        <div className="chat-markdown break-words">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {text}
          </ReactMarkdown>
          <span className="inline-block w-[2px] h-[1em] bg-accent-cyan ml-0.5 align-text-bottom animate-pulse" />
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

export function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-6">
      <div className="w-12 h-12 rounded-full bg-accent-cyan/10 flex items-center justify-center mb-4">
        <AssistantIcon />
      </div>
      <p className="text-text-muted text-sm font-medium mb-1">AI Strategist</p>
      <p className="text-text-dim text-xs max-w-[240px] mb-6">
        Ask a question about your playbook strategy and the AI will help refine it.
      </p>
      <div className="w-full max-w-[320px] text-left">
        <WorkflowSuggestions />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

export function ChatSkeleton() {
  return (
    <div className="space-y-4 p-4 animate-pulse">
      {/* Assistant message skeleton */}
      <div className="flex gap-3 flex-row">
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-accent-cyan/10" />
        <div className="rounded-lg bg-surface-alt border border-border w-[70%] h-16" />
      </div>
      {/* User message skeleton */}
      <div className="flex gap-3 flex-row-reverse">
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-accent/10" />
        <div className="rounded-lg bg-accent/10 border border-accent/20 w-[55%] h-10" />
      </div>
      {/* Assistant message skeleton */}
      <div className="flex gap-3 flex-row">
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-accent-cyan/10" />
        <div className="rounded-lg bg-surface-alt border border-border w-[65%] h-20" />
      </div>
      {/* User message skeleton */}
      <div className="flex gap-3 flex-row-reverse">
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-accent/10" />
        <div className="rounded-lg bg-accent/10 border border-accent/20 w-[45%] h-8" />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ChatMessages
// ---------------------------------------------------------------------------

export function ChatMessages({
  messages,
  isStreaming,
  streamingText,
  isLoading = false,
  toolCalls = [],
  isThinking = false,
  thinkingStatus = 'Thinking...',
  currentFinding = null,
  messageFindings = {},
  messageQuickActions = {},
  onQuickAction,
}: ChatMessagesProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new messages, streaming text, or tool call changes
  useEffect(() => {
    const el = scrollRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages, streamingText, toolCalls, isThinking, currentFinding])

  if (isLoading) {
    return (
      <div ref={scrollRef} className="flex-1 overflow-y-auto scrollbar-hide">
        <ChatSkeleton />
      </div>
    )
  }

  // Filter out system messages for display, and deduplicate consecutive
  // hidden messages (Bug: optimistic + server-persisted hidden messages
  // can overlap during streaming, producing two "Strategy generation
  // started..." placeholders).
  const displayMessages = messages.filter((m) => m.role !== 'system').filter((m, i, arr) => {
    const isHidden =
      m.extra?.hidden ||
      (m.role === 'user' && m.content.startsWith('Generate a complete GTM strategy'))
    if (!isHidden) return true
    // Keep only the first hidden message in a consecutive run
    const prev = arr[i - 1]
    if (!prev) return true
    const prevHidden =
      prev.extra?.hidden ||
      (prev.role === 'user' && prev.content.startsWith('Generate a complete GTM strategy'))
    return !prevHidden
  })
  const isAgentWorking = isStreaming || isThinking || toolCalls.length > 0 || currentFinding !== null
  const hasContent = displayMessages.length > 0 || isAgentWorking

  return (
    <div
      ref={scrollRef}
      className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide"
    >
      {!hasContent && <EmptyState />}

      {displayMessages.map((msg) => (
        <MessageBubble
          key={msg.id}
          message={msg}
          findings={messageFindings[msg.id]}
          quickActions={messageQuickActions[msg.id]}
          onQuickAction={onQuickAction}
        />
      ))}

      {/* Unified working state: thinking + tool progress in one block */}
      {(isThinking || (toolCalls && toolCalls.length > 0)) && (
        <div className="flex gap-3 flex-row">
          {/* Avatar */}
          <div className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5 bg-accent-cyan/15 text-accent-cyan">
            <AssistantIcon />
          </div>
          {/* Progress block */}
          <div className="rounded-lg px-4 py-2.5 bg-surface-alt border border-border-solid flex flex-col gap-2 max-w-[320px]">
            {/* Line 1: Pulsing dot + primary status */}
            <div className="flex items-center gap-2.5">
              <span
                className="w-2 h-2 rounded-full bg-accent-cyan flex-shrink-0"
                style={{ animation: 'thinkPulse 1.4s ease-in-out infinite' }}
              />
              <span className="text-xs text-text-muted truncate">
                {thinkingStatus || 'Thinking...'}
              </span>
            </div>
            {/* Line 2: Active tool or tool progress (if any) */}
            {toolCalls && toolCalls.length > 0 && (
              <div className="text-[11px] text-text-muted/70 pl-[18px]">
                {toolCalls.filter((t) => t.status === 'running').length > 0
                  ? `Running ${toolCalls.filter((t) => t.status === 'running').length} tool${toolCalls.filter((t) => t.status === 'running').length > 1 ? 's' : ''}...`
                  : `${toolCalls.filter((t) => t.status === 'success').length} tool${toolCalls.filter((t) => t.status === 'success').length > 1 ? 's' : ''} completed`}
              </div>
            )}
          </div>
        </div>
      )}

      {/* BL-1015: Live thinking status with latest finding */}
      <ThinkingStatus currentFinding={currentFinding} isActive={isAgentWorking && !isStreaming} />

      {/* THINK: In-flight tool call cards (AC-2, AC-4) */}
      {toolCalls.length > 0 && (
        <div className="ml-10">
          <ToolCallCardList toolCalls={toolCalls} />
        </div>
      )}

      {/* Streaming text bubble */}
      {isStreaming && streamingText && <StreamingBubble text={streamingText} />}
    </div>
  )
}
