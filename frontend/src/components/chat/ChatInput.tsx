/**
 * Shared chat input component — textarea + send button.
 * Used by both inline PlaybookChat and the global ChatPanel.
 */

import { useState, useRef, useEffect, useCallback, type KeyboardEvent } from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatInputProps {
  onSend: (text: string) => void
  isStreaming: boolean
  placeholder?: string
  /** Expose ref so parent can focus the input programmatically (Cmd+K) */
  inputRef?: React.RefObject<HTMLTextAreaElement | null>
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

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
// ChatInput
// ---------------------------------------------------------------------------

export function ChatInput({
  onSend,
  isStreaming,
  placeholder = 'Ask about your strategy...',
  inputRef: externalRef,
}: ChatInputProps) {
  const [input, setInput] = useState('')
  const internalRef = useRef<HTMLTextAreaElement>(null)
  const textareaRef = externalRef ?? internalRef

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, 160)}px`
    }
  }, [input, textareaRef])

  const handleSend = useCallback(() => {
    const trimmed = input.trim()
    if (!trimmed || isStreaming) return
    onSend(trimmed)
    setInput('')
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [input, isStreaming, onSend, textareaRef])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  return (
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
  )
}
