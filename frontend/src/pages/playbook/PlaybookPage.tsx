/**
 * PlaybookPage — split-view editor + AI chat for ICP strategy.
 *
 * Left panel (~60%): Tiptap rich-text editor (StrategyEditor)
 * Right panel (~40%): AI chat with SSE streaming (PlaybookChat)
 *
 * Shows onboarding flow for first-time visitors (no enrichment data yet).
 *
 * Wires together: usePlaybookDocument, useSavePlaybook, usePlaybookChat,
 * useExtractStrategy, useSSE, StrategyEditor, PlaybookChat, PlaybookOnboarding.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { StrategyEditor } from '../../components/playbook/StrategyEditor'
import { PlaybookChat, type ChatMessage } from '../../components/playbook/PlaybookChat'
import { PlaybookOnboarding } from '../../components/playbook/PlaybookOnboarding'
import {
  usePlaybookDocument,
  useSavePlaybook,
  usePlaybookChat,
  useExtractStrategy,
  type ChatMessage as APIChatMessage,
} from '../../api/queries/usePlaybook'
import { useSSE } from '../../hooks/useSSE'
import { resolveApiBase, buildHeaders } from '../../api/client'
import { getAccessToken } from '../../lib/auth'
import { useToast } from '../../components/ui/Toast'

// ---------------------------------------------------------------------------
// Auto-save status type
// ---------------------------------------------------------------------------

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert API ChatMessage (with `extra`) to PlaybookChat ChatMessage format. */
function toChatMessage(msg: APIChatMessage): ChatMessage {
  return {
    id: msg.id,
    role: msg.role,
    content: msg.content,
    created_at: msg.created_at,
  }
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function ExtractIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 2v8M5 7l3 3 3-3" />
      <path d="M2 11v2a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-2" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// PlaybookPage
// ---------------------------------------------------------------------------

export function PlaybookPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  // Server state
  const docQuery = usePlaybookDocument()
  const chatQuery = usePlaybookChat()
  const saveMutation = useSavePlaybook()
  const extractMutation = useExtractStrategy()

  // SSE streaming
  const sse = useSSE()

  // Local state
  const [editedContent, setEditedContent] = useState<string | null>(null)
  const [streamingText, setStreamingText] = useState('')
  const [optimisticMessages, setOptimisticMessages] = useState<ChatMessage[]>([])
  const [isDirty, setIsDirty] = useState(false)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [skipped, setSkipped] = useState(false)

  // Refs for debounced auto-save
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latestContentRef = useRef<string | null>(null)

  // Poll for content when document has enrichment_id but empty content
  // (race condition: research completed before template was seeded)
  useEffect(() => {
    if (!docQuery.data) return
    const hasEnrichment = !!docQuery.data.enrichment_id
    const hasContent = !!(docQuery.data.content && docQuery.data.content.trim().length > 0)
    if (hasEnrichment && !hasContent && !isDirty) {
      const interval = setInterval(() => {
        docQuery.refetch()
      }, 2000)
      return () => clearInterval(interval)
    }
  }, [docQuery.data?.enrichment_id, docQuery.data?.content, isDirty])

  // Derive localContent: user edits take priority over server data
  const localContent = isDirty
    ? editedContent
    : (docQuery.data?.content ?? null)

  // ---------------------------------------------------------------------------
  // Auto-save logic
  // ---------------------------------------------------------------------------

  const performSave = useCallback(async (content: string) => {
    setSaveStatus('saving')
    try {
      await saveMutation.mutateAsync({ content })
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus((s) => s === 'saved' ? 'idle' : s), 2000)
    } catch {
      setSaveStatus('error')
      toast('Failed to save', 'error')
    }
  }, [saveMutation, toast])

  const scheduleSave = useCallback((content: string) => {
    latestContentRef.current = content
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
    }
    debounceTimerRef.current = setTimeout(() => {
      const c = latestContentRef.current
      if (c !== null) {
        performSave(c)
      }
    }, 1500)
  }, [performSave])

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Editor handlers
  // ---------------------------------------------------------------------------

  const handleEditorUpdate = useCallback((content: string) => {
    setEditedContent(content)
    setIsDirty(true)
    setSaveStatus('idle')
    scheduleSave(content)
  }, [scheduleSave])

  // Cmd/Ctrl+S: flush pending save immediately
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        if (debounceTimerRef.current) {
          clearTimeout(debounceTimerRef.current)
        }
        const c = latestContentRef.current
        if (c !== null) {
          performSave(c)
        }
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [performSave])

  // ---------------------------------------------------------------------------
  // Extract handler
  // ---------------------------------------------------------------------------

  const handleExtract = useCallback(async () => {
    try {
      await extractMutation.mutateAsync()
      toast('Strategy data extracted successfully', 'success')
    } catch {
      toast('Extraction failed', 'error')
    }
  }, [extractMutation, toast])

  // ---------------------------------------------------------------------------
  // Chat handlers
  // ---------------------------------------------------------------------------

  const handleSendMessage = useCallback(
    (text: string) => {
      // Add optimistic user message
      const optimisticMsg: ChatMessage = {
        id: `optimistic-${Date.now()}`,
        role: 'user',
        content: text,
        created_at: new Date().toISOString(),
      }
      setOptimisticMessages((prev) => [...prev, optimisticMsg])
      setStreamingText('')

      const url = `${resolveApiBase()}/playbook/chat`
      const token = getAccessToken()
      const headers = buildHeaders(token)

      sse.startStream(url, { message: text }, headers, {
        onChunk: (chunk) => {
          setStreamingText((prev) => prev + chunk)
        },
        onDone: () => {
          setStreamingText('')
          setOptimisticMessages([])
          // Refetch chat history from server to get persisted messages
          chatQuery.refetch()
        },
        onError: (error) => {
          setStreamingText('')
          setOptimisticMessages([])
          toast(error.message || 'Chat error', 'error')
        },
      })
    },
    [sse, chatQuery, toast],
  )

  // ---------------------------------------------------------------------------
  // Derived state
  // ---------------------------------------------------------------------------

  const serverMessages = (chatQuery.data?.messages ?? []).map(toChatMessage)
  const allMessages = [...serverMessages, ...optimisticMessages]

  // ---------------------------------------------------------------------------
  // Loading / error states
  // ---------------------------------------------------------------------------

  if (docQuery.isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-border border-t-accent rounded-full animate-spin" />
          <p className="text-sm text-text-muted">Loading playbook...</p>
        </div>
      </div>
    )
  }

  if (docQuery.isError) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="w-12 h-12 rounded-full bg-error/10 flex items-center justify-center">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-error">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4M12 16h.01" />
            </svg>
          </div>
          <p className="text-sm text-error font-medium">Failed to load playbook</p>
          <p className="text-xs text-text-dim max-w-[300px]">
            {docQuery.error instanceof Error ? docQuery.error.message : 'Unknown error'}
          </p>
          <button
            onClick={() => docQuery.refetch()}
            className="px-3 py-1.5 text-xs font-medium text-accent border border-accent/30 rounded-md hover:bg-accent/10 transition-colors bg-transparent cursor-pointer"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Onboarding gate — show if no enrichment data and user hasn't skipped
  // ---------------------------------------------------------------------------

  const needsOnboarding = docQuery.data && !docQuery.data.enrichment_id

  if (needsOnboarding && !skipped) {
    return (
      <PlaybookOnboarding
        onSkip={() => setSkipped(true)}
        onComplete={() => {
          // Invalidate the document query so it re-fetches with seeded content.
          // Only invalidate ['playbook'] exactly — NOT ['playbook', 'research']
          // which would cause the onboarding to skip prematurely (see 8ac309b).
          queryClient.invalidateQueries({ queryKey: ['playbook'], exact: true })
        }}
      />
    )
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Top bar */}
      <div className="flex items-center gap-3 mb-3 flex-shrink-0">
        <h1 className="font-title text-[1.3rem] font-semibold tracking-tight">
          ICP Playbook
        </h1>

        {/* Auto-save status */}
        <div className="flex items-center gap-1.5 ml-2">
          {saveStatus === 'saving' && (
            <span className="text-xs text-text-muted animate-pulse">
              Saving...
            </span>
          )}
          {saveStatus === 'saved' && (
            <span className="text-xs text-success font-medium animate-[fadeIn_0.2s_ease-out]">
              Saved
            </span>
          )}
          {saveStatus === 'error' && (
            <span className="text-xs text-error font-medium">
              Save failed
            </span>
          )}
        </div>

        <div className="ml-auto flex items-center gap-2">
          {/* Extract button */}
          <button
            onClick={handleExtract}
            disabled={extractMutation.isPending || saveStatus === 'saving'}
            title={saveStatus === 'saving' ? 'Waiting for save...' : 'Extract structured data from strategy'}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors bg-transparent border cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed border-accent-cyan/30 text-accent-cyan hover:bg-accent-cyan/10"
          >
            <ExtractIcon />
            {extractMutation.isPending ? 'Extracting...' : 'Extract'}
          </button>
        </div>
      </div>

      {/* Split layout */}
      <div className="flex gap-4 flex-1 min-h-0">
        {/* Left: Editor */}
        <div className="flex-[3] min-w-0 flex flex-col min-h-0">
          <div className="flex-1 min-h-0 overflow-y-auto">
            <StrategyEditor
              content={localContent}
              onUpdate={handleEditorUpdate}
            />
          </div>
        </div>

        {/* Right: Chat */}
        <div className="flex-[2] min-w-0 flex flex-col min-h-0">
          <PlaybookChat
            messages={allMessages}
            onSendMessage={handleSendMessage}
            isStreaming={sse.isStreaming}
            streamingText={streamingText}
          />
        </div>
      </div>
    </div>
  )
}
