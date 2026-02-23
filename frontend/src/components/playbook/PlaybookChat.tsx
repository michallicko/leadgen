/**
 * PlaybookChat — chat panel for playbook AI conversations.
 *
 * Presentational component: receives messages + streaming state from parent,
 * delegates send action upward. Auto-scrolls to bottom on new content.
 */

import { useState, useRef, useEffect, useCallback, type KeyboardEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

interface PlaybookChatProps {
  messages: ChatMessage[]
  onSendMessage: (message: string) => void
  isStreaming: boolean
  streamingText: string
  /** Phase-specific placeholder text for the input */
  placeholder?: string
  /** When set, shows the active tool name below "Thinking..." (e.g., "Reading strategy...") */
  activeToolName?: string | null
}

// ---------------------------------------------------------------------------
// Icons (inline SVG — keeps the component self-contained)
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

function SendIcon() {
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
      <path d="M14 2L7 9" />
      <path d="M14 2L9.5 14L7 9L2 6.5L14 2Z" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'

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
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2.5 text-sm leading-relaxed ${
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
// Empty state
// ---------------------------------------------------------------------------

function EmptyState() {
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
// PlaybookChat
// ---------------------------------------------------------------------------

export function PlaybookChat({
  messages,
  onSendMessage,
  isStreaming,
  streamingText,
  placeholder = 'Ask about your strategy...',
  activeToolName = null,
}: PlaybookChatProps) {
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to bottom on new messages or streaming text changes
  useEffect(() => {
    const el = scrollRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages, streamingText])

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, 160)}px`
    }
  }, [input])

  const handleSend = useCallback(() => {
    const trimmed = input.trim()
    if (!trimmed || isStreaming) return
    onSendMessage(trimmed)
    setInput('')
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [input, isStreaming, onSendMessage])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  const hasContent = messages.length > 0 || isStreaming

  return (
    <div className="flex flex-col h-full bg-surface rounded-lg border border-border-solid overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border-solid bg-surface">
        <div className="w-2 h-2 rounded-full bg-accent-cyan" />
        <h3 className="text-sm font-semibold font-title text-text">AI Chat</h3>
        {isStreaming && (
          <div className="ml-auto flex flex-col items-end">
            <span className="text-[11px] text-accent-cyan animate-pulse">
              Thinking...
            </span>
            {activeToolName && (
              <span className="text-[10px] text-text-dim">
                {activeToolName}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Message list */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide"
      >
        {!hasContent && <EmptyState />}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {isStreaming && streamingText && <StreamingBubble text={streamingText} />}
      </div>

      {/* Input area */}
      <div className="border-t border-border-solid p-3 bg-surface">
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            rows={1}
            disabled={isStreaming}
            className="flex-1 resize-none rounded-lg bg-surface-alt border border-border-solid px-3 py-2 text-sm text-text placeholder:text-text-dim focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-colors disabled:opacity-50"
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
            className="flex-shrink-0 w-9 h-9 flex items-center justify-center rounded-lg bg-accent text-white transition-colors hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="Send message"
          >
            <SendIcon />
          </button>
        </div>
        <p className="text-[11px] text-text-dim mt-1.5 px-1">
          Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  )
}
