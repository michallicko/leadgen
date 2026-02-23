/**
 * ChatProvider — app-level context for persistent chat.
 *
 * Wraps the router so chat state persists across route changes.
 * Manages: messages, streaming, open/closed state, page context.
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
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../hooks/useAuth'
import { usePlaybookChat, useNewThread } from '../api/queries/usePlaybook'
import { useSSE } from '../hooks/useSSE'
import { resolveApiBase, buildHeaders } from '../api/client'
import { getAccessToken } from '../lib/auth'
import type { ChatMessage } from '../components/chat/ChatMessages'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatContextValue {
  // State
  messages: ChatMessage[]
  isOpen: boolean
  isStreaming: boolean
  streamingText: string
  isLoading: boolean

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
  const queryClient = useQueryClient()
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

      const url = `${resolveApiBase()}/playbook/chat`
      const token = getAccessToken()
      const headers = buildHeaders(token)

      sse.startStream(
        url,
        { message: text, page_context: currentPage },
        headers,
        {
          onChunk: (chunk) => {
            setStreamingText((prev) => prev + chunk)
          },
          onDone: () => {
            setStreamingText('')
            setOptimisticMessages([])
            chatQuery.refetch()
          },
          onError: () => {
            setStreamingText('')
            setOptimisticMessages([])
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
