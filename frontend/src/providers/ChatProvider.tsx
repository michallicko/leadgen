/**
 * ChatProvider — app-level context for persistent chat.
 *
 * Wraps the router so chat state persists across route changes.
 * Manages: messages, streaming, open/closed state, page context,
 * tool call state (thinking indicator, in-flight tool calls).
 *
 * On the Playbook page the inline chat is used instead of the sliding panel.
 * Cmd+K toggles the panel (or focuses inline input on Playbook page).
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  type ReactNode,
} from 'react'
import { useLocation } from 'react-router'
import { useAuth } from '../hooks/useAuth'
import { usePlaybookChat, useNewThread } from '../api/queries/usePlaybook'
import { useSSE } from '../hooks/useSSE'
import { resolveApiBase, buildHeaders } from '../api/client'
import { getAccessToken } from '../lib/auth'
import type { ChatMessage } from '../components/chat/ChatMessages'
import type { ToolCallEvent } from '../components/playbook/ToolCallCard'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Summary of a document change triggered by AI tool calls. */
export interface DocumentChangeInfo {
  changed: boolean
  summary: string | null
}

interface ChatContextValue {
  // State
  messages: ChatMessage[]
  isOpen: boolean
  isStreaming: boolean
  streamingText: string
  isLoading: boolean

  /** Set after an AI turn completes with strategy edits. Cleared on next send. */
  documentChanged: DocumentChangeInfo | null
  clearDocumentChanged: () => void
  // Tool call state (THINK feature)
  toolCalls: ToolCallEvent[]
  isThinking: boolean
  activeToolName: string | null

  // Actions
  toggleChat: () => void
  openChat: () => void
  closeChat: () => void
  sendMessage: (text: string) => void
  startNewThread: () => void

  // Context
  currentPage: string
  isOnPlaybookPage: boolean

  // Ref for Cmd+K focus on inline input
  chatInputRef: React.RefObject<HTMLTextAreaElement | null>
}

const ChatContext = createContext<ChatContextValue | null>(null)

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------

const PANEL_OPEN_KEY = 'chat_panel_open'
const LAST_SEEN_KEY = 'chat_last_seen_msg'

function getStoredOpen(): boolean {
  try {
    return localStorage.getItem(PANEL_OPEN_KEY) === 'true'
  } catch {
    return false
  }
}

function setStoredOpen(open: boolean) {
  try {
    localStorage.setItem(PANEL_OPEN_KEY, String(open))
  } catch {
    // localStorage unavailable
  }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function ChatProvider({ children }: { children: ReactNode }) {
  const location = useLocation()
  const { isAuthenticated } = useAuth()

  // Server state — only fetch when authenticated
  const chatQuery = usePlaybookChat(isAuthenticated)
  const newThreadMutation = useNewThread()

  // SSE streaming
  const sse = useSSE()

  // Local state
  const [isOpen, setIsOpen] = useState(getStoredOpen)
  const [streamingText, setStreamingText] = useState('')
  const [optimisticMessages, setOptimisticMessages] = useState<ChatMessage[]>([])
  const [documentChanged, setDocumentChanged] = useState<DocumentChangeInfo | null>(null)

  const clearDocumentChanged = useCallback(() => setDocumentChanged(null), [])

  // Tool call state (THINK feature)
  const [toolCalls, setToolCalls] = useState<ToolCallEvent[]>([])
  const [isThinking, setIsThinking] = useState(false)
  const [activeToolName, setActiveToolName] = useState<string | null>(null)

  // Ref for inline chat input (Cmd+K focus)
  const chatInputRef = useRef<HTMLTextAreaElement>(null)

  // Derive current page from router location
  const currentPage = useMemo(() => {
    const segments = location.pathname.split('/').filter(Boolean)
    // URL: /:namespace/:page/...
    return segments[1] || 'unknown'
  }, [location.pathname])

  const isOnPlaybookPage = currentPage === 'playbook'

  // ---------------------------------------------------------------------------
  // Panel open/close
  // ---------------------------------------------------------------------------

  const toggleChat = useCallback(() => {
    setIsOpen((prev) => {
      const next = !prev
      setStoredOpen(next)
      return next
    })
  }, [])

  const openChat = useCallback(() => {
    setIsOpen(true)
    setStoredOpen(true)
  }, [])

  const closeChat = useCallback(() => {
    setIsOpen(false)
    setStoredOpen(false)
  }, [])

  // ---------------------------------------------------------------------------
  // Track last seen message for unread badge
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (isOpen && chatQuery.data?.messages) {
      const msgs = chatQuery.data.messages
      if (msgs.length > 0) {
        const lastMsg = msgs[msgs.length - 1]
        try {
          localStorage.setItem(LAST_SEEN_KEY, lastMsg.id)
        } catch {
          // ignore
        }
      }
    }
  }, [isOpen, chatQuery.data?.messages])

  // ---------------------------------------------------------------------------
  // Send message
  // ---------------------------------------------------------------------------

  const sendMessage = useCallback(
    (text: string) => {
      // Add optimistic user message
      const optimisticMsg: ChatMessage = {
        id: `optimistic-${Date.now()}`,
        role: 'user',
        content: text,
        created_at: new Date().toISOString(),
        page_context: currentPage,
      }
      setOptimisticMessages((prev) => [...prev, optimisticMsg])
      setStreamingText('')
      setToolCalls([])
      setIsThinking(true)
      setActiveToolName(null)

      const url = `${resolveApiBase()}/playbook/chat`
      const token = getAccessToken()
      const headers = buildHeaders(token)

      // Clear any previous document change before starting new stream
      setDocumentChanged(null)

      sse.startStream(
        url,
        { message: text, page_context: currentPage },
        headers,
        {
          onChunk: (chunk) => {
            setIsThinking(false)
            setStreamingText((prev) => prev + chunk)
          },
          onDone: (doneData) => {
            setStreamingText('')
            setOptimisticMessages([])
            setToolCalls([])
            setIsThinking(false)
            setActiveToolName(null)
            chatQuery.refetch()

            // Detect document changes from strategy tool calls
            const doneToolCalls = doneData.toolCalls
            if (doneToolCalls && doneToolCalls.length > 0) {
              const STRATEGY_EDIT_TOOLS = new Set([
                'update_strategy_section',
                'set_extracted_field',
                'append_to_section',
              ])
              const edits = doneToolCalls.filter(
                (tc) => STRATEGY_EDIT_TOOLS.has(tc.tool_name) && tc.status === 'success',
              )
              if (edits.length > 0) {
                const names = edits.map((tc) => tc.tool_name.replace(/_/g, ' '))
                setDocumentChanged({
                  changed: true,
                  summary:
                    edits.length === 1
                      ? `Strategy updated (${names[0]})`
                      : `Strategy updated (${edits.length} changes)`,
                })
              }
            }
          },
          onError: () => {
            setStreamingText('')
            setOptimisticMessages([])
            setToolCalls([])
            setIsThinking(false)
            setActiveToolName(null)
          },
          onToolStart: (event) => {
            setIsThinking(false)
            setActiveToolName(event.toolName)
            setToolCalls((prev) => [
              ...prev,
              {
                tool_call_id: event.toolCallId,
                tool_name: event.toolName,
                input: event.input,
                status: 'running',
              },
            ])
          },
          onToolResult: (result) => {
            setToolCalls((prev) =>
              prev.map((tc) =>
                tc.tool_call_id === result.toolCallId
                  ? {
                      ...tc,
                      status: result.status,
                      summary: result.summary,
                      output: result.output,
                      duration_ms: result.durationMs,
                    }
                  : tc,
              ),
            )
            // Clear active tool name when result arrives
            setActiveToolName(null)
          },
          onThinking: () => {
            setIsThinking(false)
          },
        },
      )
    },
    [sse, chatQuery, currentPage],
  )

  // ---------------------------------------------------------------------------
  // New thread
  // ---------------------------------------------------------------------------

  const startNewThread = useCallback(() => {
    newThreadMutation.mutate(undefined)
  }, [newThreadMutation])

  // ---------------------------------------------------------------------------
  // Cmd+K shortcut
  // ---------------------------------------------------------------------------

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()

        if (isOnPlaybookPage) {
          // Focus the inline chat input
          chatInputRef.current?.focus()
          return
        }

        // Toggle the sliding panel
        toggleChat()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [isOnPlaybookPage, toggleChat])

  // ---------------------------------------------------------------------------
  // Derived messages
  // ---------------------------------------------------------------------------

  const serverMessages: ChatMessage[] = useMemo(() => {
    return (chatQuery.data?.messages ?? []).map((msg) => ({
      id: msg.id,
      role: msg.role as ChatMessage['role'],
      content: msg.content,
      extra: msg.extra,
      created_at: msg.created_at,
      page_context: msg.page_context,
      thread_start: msg.thread_start,
    }))
  }, [chatQuery.data?.messages])

  const allMessages = useMemo(
    () => [...serverMessages, ...optimisticMessages],
    [serverMessages, optimisticMessages],
  )

  // ---------------------------------------------------------------------------
  // Context value
  // ---------------------------------------------------------------------------

  const value = useMemo<ChatContextValue>(
    () => ({
      messages: allMessages,
      isOpen,
      isStreaming: sse.isStreaming,
      streamingText,
      isLoading: chatQuery.isLoading,
      documentChanged,
      clearDocumentChanged,
      toolCalls,
      isThinking,
      activeToolName,
      toggleChat,
      openChat,
      closeChat,
      sendMessage,
      startNewThread,
      currentPage,
      isOnPlaybookPage,
      chatInputRef,
    }),
    [
      allMessages,
      isOpen,
      sse.isStreaming,
      streamingText,
      chatQuery.isLoading,
      documentChanged,
      clearDocumentChanged,
      toolCalls,
      isThinking,
      activeToolName,
      toggleChat,
      openChat,
      closeChat,
      sendMessage,
      startNewThread,
      currentPage,
      isOnPlaybookPage,
    ],
  )

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useChatContext(): ChatContextValue {
  const ctx = useContext(ChatContext)
  if (!ctx) {
    throw new Error('useChatContext must be used within a ChatProvider')
  }
  return ctx
}

/**
 * Check if there are unread messages (AI responded while panel was closed).
 * Returns true if the latest assistant message ID differs from localStorage.
 */
export function useHasUnread(): boolean {
  const { messages, isOpen } = useChatContext()

  return useMemo(() => {
    if (isOpen) return false

    const lastAssistant = [...messages]
      .reverse()
      .find((m) => m.role === 'assistant')

    if (!lastAssistant) return false

    try {
      const lastSeen = localStorage.getItem(LAST_SEEN_KEY)
      return lastSeen !== lastAssistant.id
    } catch {
      return false
    }
  }, [messages, isOpen])
}
