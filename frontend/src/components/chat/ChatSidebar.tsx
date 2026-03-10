/**
 * ChatSidebar -- unified right-side chat panel for all pages.
 *
 * Replaces both ChatPanel (overlay) and PlaybookChat (inline).
 * Lives in AppShell as a flex sibling that pushes content.
 *
 * Two states:
 *   Expanded: w-[400px] xl / w-[320px] md -- full chat UI
 *   Collapsed: w-[40px] thin strip with chat icon + unread badge
 *
 * Uses useChatContext() for all state.
 */

import { useChatContext, useHasUnread } from '../../providers/ChatProvider'
import { useNudgeCount } from '../../hooks/useWorkflowSuggestions'
import { ChatMessages } from './ChatMessages'
import { ChatInput } from './ChatInput'
import { WelcomeBackBanner } from './WelcomeBackBanner'
import { WorkflowSuggestionChips } from './WorkflowSuggestions'

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function CollapseIcon() {
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
      <path d="M6 3l5 5-5 5" />
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

function ChatIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="w-5 h-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// ChatSidebar
// ---------------------------------------------------------------------------

export function ChatSidebar() {
  const {
    messages,
    isOpen,
    isStreaming,
    streamingText,
    isLoading,
    toggleChat,
    sendMessage,
    startNewThread,
    chatInputRef,
    toolCalls,
    isThinking,
    thinkingStatus,
    currentPage,
    isOnPlaybookPage,
  } = useChatContext()

  const hasUnread = useHasUnread()
  const { data: nudgeCount = 0 } = useNudgeCount(!isOnPlaybookPage)

  // Context-aware placeholder based on current page
  const PAGE_PLACEHOLDERS: Record<string, string> = {
    playbook: 'Ask about your GTM strategy...',
    contacts: 'Ask about your contacts or targeting criteria...',
    companies: 'Ask about companies in your pipeline...',
    messages: 'Help me craft outreach messages...',
    campaigns: 'Ask about your campaign settings...',
    enrich: 'Ask about enrichment or data quality...',
    import: 'Ask about importing contacts...',
  }
  const placeholder = PAGE_PLACEHOLDERS[currentPage] ?? 'How can I help?'

  // Badge logic for collapsed state
  const showNudgeBadge = !isOpen && nudgeCount > 0
  const showUnreadDot = hasUnread && !showNudgeBadge

  return (
    <div
      className={`flex-shrink-0 border-l border-border bg-surface transition-all duration-300 ease-in-out ${
        isOpen ? 'w-[320px] xl:w-[400px]' : 'w-[40px]'
      }`}
      role="complementary"
      aria-label="AI Chat Sidebar"
    >
      {/* Collapsed state -- icon tab */}
      {!isOpen && (
        <div className="flex flex-col items-center h-full pt-3">
          <button
            onClick={toggleChat}
            className="relative p-2 rounded-md text-text-muted hover:text-accent-cyan hover:bg-surface-alt transition-colors bg-transparent border-none cursor-pointer"
            aria-label="Open AI Chat (Cmd+K)"
            title="Open AI Chat (Cmd+K)"
          >
            <ChatIcon />
            {showNudgeBadge && (
              <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 flex items-center justify-center bg-accent-cyan text-white text-[10px] font-bold rounded-full leading-none">
                {nudgeCount}
              </span>
            )}
            {showUnreadDot && (
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-accent-cyan rounded-full" />
            )}
          </button>
        </div>
      )}

      {/* Expanded state -- full chat UI */}
      {isOpen && (
        <div className="flex flex-col h-full overflow-hidden">
          {/* Header */}
          <div className="flex items-center gap-2 px-4 py-3 border-b border-border-solid bg-surface flex-shrink-0">
            <div className="w-2 h-2 rounded-full bg-accent-cyan" />
            <h3 className="text-sm font-semibold font-title text-text">
              AI Strategist
            </h3>
            {isStreaming && (
              <span className="text-[11px] text-accent-cyan animate-pulse truncate max-w-[140px]">
                {thinkingStatus}
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

              {/* Collapse button */}
              <button
                onClick={toggleChat}
                className="p-1.5 rounded-md text-text-muted hover:text-text hover:bg-surface-alt transition-colors bg-transparent border-none cursor-pointer"
                title="Collapse chat (Cmd+K)"
                aria-label="Collapse chat sidebar"
              >
                <CollapseIcon />
              </button>
            </div>
          </div>

          {/* Welcome back banner */}
          <WelcomeBackBanner />

          {/* Messages */}
          <ChatMessages
            messages={messages}
            isStreaming={isStreaming}
            streamingText={streamingText}
            isLoading={isLoading}
            toolCalls={toolCalls}
            isThinking={isThinking}
            thinkingStatus={thinkingStatus}
          />

          {/* Suggestion chips */}
          <WorkflowSuggestionChips />

          {/* Input */}
          <ChatInput
            onSend={sendMessage}
            isStreaming={isStreaming}
            placeholder={placeholder}
            inputRef={chatInputRef}
          />

          {/* Keyboard shortcut hint */}
          <div className="px-3 pb-2 flex-shrink-0">
            <p className="text-[10px] text-text-dim text-center">
              Cmd+K to toggle
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
