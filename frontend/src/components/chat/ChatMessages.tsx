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
import { ToolCallCardList, type ToolCallEvent } from '../playbook/ToolCallCard'
import { ThinkingIndicator } from '../playbook/ThinkingIndicator'

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

function getPersistedToolCalls(message: ChatMessage): ToolCallEvent[] | null {
  const extra = message.extra
  if (!extra || !Array.isArray(extra.tool_calls) || extra.tool_calls.length === 0) {
    return null
  }

  return (extra.tool_calls as Array<Record<string, unknown>>).map((tc, idx) => ({
    tool_call_id: (tc.tool_call_id as string) || (tc.id as string) || `persisted-${idx}`,
    tool_name: (tc.tool_name as string) || (tc.name as string) || 'unknown',
    input: (tc.input_args as Record<string, unknown>) || (tc.input as Record<string, unknown>) || {},
    status: ((tc.status as string) === 'error' ? 'error' : 'success') as 'success' | 'error',
    summary: (tc.summary as string) || undefined,
    output: (tc.output_data as Record<string, unknown>) || (tc.output as Record<string, unknown>) || undefined,
    duration_ms: (tc.duration_ms as number) || undefined,
  }))
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'

  // Don't render system messages (thread boundaries)
  if (message.role === 'system') return null

  // AC-6: Render persisted tool calls from message metadata
  const persistedToolCalls = !isUser ? getPersistedToolCalls(message) : null

  return (
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
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
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
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
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
      <p className="text-text-muted text-sm font-medium mb-1">No messages yet</p>
      <p className="text-text-dim text-xs max-w-[240px]">
        Ask a question about your playbook strategy and the AI will help refine it.
      </p>
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
}: ChatMessagesProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new messages, streaming text, or tool call changes
  useEffect(() => {
    const el = scrollRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages, streamingText, toolCalls, isThinking])

  if (isLoading) {
    return (
      <div ref={scrollRef} className="flex-1 overflow-y-auto scrollbar-hide">
        <ChatSkeleton />
      </div>
    )
  }

  // Filter out system messages for display
  const displayMessages = messages.filter((m) => m.role !== 'system')
  const hasContent = displayMessages.length > 0 || isStreaming || isThinking || toolCalls.length > 0

  return (
    <div
      ref={scrollRef}
      className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide"
    >
      {!hasContent && <EmptyState />}

      {displayMessages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}

      {/* THINK: Thinking indicator (AC-1: before first tool_start or chunk) */}
      {isThinking && <ThinkingIndicator />}

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
