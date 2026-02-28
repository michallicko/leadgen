/**
 * ChatPanel — sliding right-side panel for app-wide chat.
 *
 * Renders inside AppShell so it only appears for authenticated users.
 * Overlays on top of page content (does NOT push). Slides in/out with
 * CSS transition. z-30 (below modals at z-40, above page content).
 *
 * Responsive:
 *   Desktop (>1200px): 400px width
 *   Tablet (768-1200px): 320px width
 *   Mobile (<768px): full-screen overlay
 *
 * Does NOT close on outside click (intentional persistent behavior).
 */

import { useChatContext } from '../../providers/ChatProvider'
import { ChatMessages } from './ChatMessages'
import { ChatInput } from './ChatInput'

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function CloseIcon() {
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
      <path d="M4 4l8 8M12 4l-8 8" />
    </svg>
  )
}

function NewThreadIcon() {
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
      <path d="M8 3v10M3 8h10" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// ChatPanel
// ---------------------------------------------------------------------------

export function ChatPanel() {
  const {
    messages,
    isOpen,
    isStreaming,
    streamingText,
    isLoading,
    closeChat,
    sendMessage,
    startNewThread,
    isOnPlaybookPage,
    chatInputRef,
    toolCalls,
    isThinking,
  } = useChatContext()

  // Don't render on Playbook page — inline chat is used there
  if (isOnPlaybookPage) return null

  return (
    <>
      {/* Backdrop for mobile only */}
      <div
        className={`fixed inset-0 bg-black/30 z-[29] transition-opacity duration-200 md:hidden ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={closeChat}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        className={`fixed top-0 right-0 h-full z-30 flex flex-col bg-surface border-l border-border-solid shadow-xl transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        } w-full md:w-[320px] xl:w-[400px]`}
        role="complementary"
        aria-label="AI Chat Panel"
      >
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border-solid bg-surface flex-shrink-0">
          <div className="w-2 h-2 rounded-full bg-accent-cyan" />
          <h3 className="text-sm font-semibold font-title text-text">
            AI Strategist
          </h3>
          {isStreaming && (
            <span className="text-[11px] text-accent-cyan animate-pulse">
              Thinking...
            </span>
          )}

          <div className="ml-auto flex items-center gap-1">
            {/* New conversation button */}
            <button
              onClick={startNewThread}
              className="p-1.5 rounded-md text-text-muted hover:text-text hover:bg-surface-alt transition-colors bg-transparent border-none cursor-pointer"
              title="New conversation"
              aria-label="Start new conversation"
            >
              <NewThreadIcon />
            </button>

            {/* Close button */}
            <button
              onClick={closeChat}
              className="p-1.5 rounded-md text-text-muted hover:text-text hover:bg-surface-alt transition-colors bg-transparent border-none cursor-pointer"
              title="Close chat (Cmd+K)"
              aria-label="Close chat panel"
            >
              <CloseIcon />
            </button>
          </div>
        </div>

        {/* Messages */}
        <ChatMessages
          messages={messages}
          isStreaming={isStreaming}
          streamingText={streamingText}
          isLoading={isLoading}
          toolCalls={toolCalls}
          isThinking={isThinking}
        />

        {/* Input */}
        <ChatInput
          onSend={sendMessage}
          isStreaming={isStreaming}
          placeholder="Ask anything about your strategy..."
          inputRef={chatInputRef}
        />

        {/* Keyboard shortcut hint */}
        <div className="px-3 pb-2 flex-shrink-0">
          <p className="text-[10px] text-text-dim text-center hidden md:block">
            Cmd+K to toggle
          </p>
        </div>
      </div>
    </>
  )
}
