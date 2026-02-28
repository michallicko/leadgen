/**
 * PlaybookChat — inline chat panel for the playbook page.
 *
 * Thin wrapper around shared ChatMessages + ChatInput components.
 * Provides the playbook-specific header and layout chrome.
 *
 * THINK feature: passes toolCalls and isThinking props through to
 * ChatMessages for real-time tool call visualization.
 */

import { ChatMessages, type ChatMessage } from '../chat/ChatMessages'
import { ChatInput } from '../chat/ChatInput'
import type { ToolCallEvent } from './ToolCallCard'

// Re-export ChatMessage type for consumers
export type { ChatMessage }

interface PlaybookChatProps {
  messages: ChatMessage[]
  onSendMessage: (message: string) => void
  isStreaming: boolean
  streamingText: string
  /** Phase-specific placeholder text for the input */
  placeholder?: string
  /** When set, shows the active tool name below "Thinking..." (e.g., "Reading strategy...") */
  activeToolName?: string | null
  /** Loading state for skeleton */
  isLoading?: boolean
  /** Ref forwarded to the textarea for Cmd+K focus */
  inputRef?: React.RefObject<HTMLTextAreaElement | null>
  /** THINK: in-flight tool calls from the current agent turn */
  toolCalls?: ToolCallEvent[]
  /** THINK: show thinking indicator before first tool_start or chunk */
  isThinking?: boolean
  /** Clickable suggestion chips shown above the input */
  suggestions?: string[]
}

export function PlaybookChat({
  messages,
  onSendMessage,
  isStreaming,
  streamingText,
  placeholder = 'Ask about your strategy...',
  activeToolName = null,
  isLoading = false,
  inputRef,
  toolCalls = [],
  isThinking = false,
  suggestions = [],
}: PlaybookChatProps) {
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
      <ChatMessages
        messages={messages}
        isStreaming={isStreaming}
        streamingText={streamingText}
        isLoading={isLoading}
        toolCalls={toolCalls}
        isThinking={isThinking}
      />

      {/* Suggestion chips */}
      {suggestions.length > 0 && !isStreaming && (
        <div className="px-3 pt-2 flex flex-wrap gap-2">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => onSendMessage(suggestion)}
              className="px-3 py-1.5 text-xs font-medium rounded-full border border-accent/30 text-accent hover:bg-accent/10 transition-colors bg-transparent cursor-pointer"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      {/* Input area */}
      <ChatInput
        onSend={onSendMessage}
        isStreaming={isStreaming}
        placeholder={placeholder}
        inputRef={inputRef}
      />
    </div>
  )
}
