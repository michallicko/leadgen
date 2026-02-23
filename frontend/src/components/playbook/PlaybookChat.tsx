/**
 * PlaybookChat — inline chat panel for the playbook page.
 *
 * Thin wrapper around shared ChatMessages + ChatInput components.
 * Provides the playbook-specific header and layout chrome.
 */

import { ChatMessages, type ChatMessage } from '../chat/ChatMessages'
import { ChatInput } from '../chat/ChatInput'

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
      />

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
