/**
 * PlaybookPage — split-view editor + AI chat for ICP strategy.
 *
 * Left panel (~60%): Phase-specific content (StrategyEditor for strategy, placeholders for others)
 * Right panel (~40%): AI chat with SSE streaming (PlaybookChat)
 *
 * Shows onboarding flow for first-time visitors (no enrichment data yet).
 *
 * Wires together: usePlaybookDocument, useSavePlaybook, usePlaybookChat,
 * useExtractStrategy, useSSE, PhaseIndicator, PhasePanel, PlaybookChat, PlaybookOnboarding.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { PhaseIndicator, PHASE_ORDER, type PhaseKey } from '../../components/playbook/PhaseIndicator'
import { PhasePanel } from '../../components/playbook/PhasePanel'
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

function isValidPhase(phase: string | undefined): phase is PhaseKey {
  return PHASE_ORDER.includes(phase as PhaseKey)
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
// Phase-specific placeholder text for chat input
// ---------------------------------------------------------------------------

const PHASE_PLACEHOLDERS: Record<string, string> = {
  strategy: 'Ask about your ICP strategy...',
  contacts: 'Which contacts should we target?',
  messages: "Let's craft your outreach messages...",
  campaign: 'Configure your campaign...',
}

// ---------------------------------------------------------------------------
// Phase-specific action button labels
// ---------------------------------------------------------------------------

/**
 * Human-readable display names for tool calls.
 * Each tool spec adds entries here when its tools are registered.
 * AGENT ships with an empty map; WRITE/SEARCH/etc. add theirs.
 */
const TOOL_DISPLAY_NAMES: Record<string, string> = {
  // Populated by tool specs (WRITE, SEARCH, etc.)
  // Example: get_strategy: 'Reading strategy...'
}

/** Get a display-friendly name for a tool, falling back to the raw name. */
function getToolDisplayName(toolName: string): string {
  return TOOL_DISPLAY_NAMES[toolName] || `Running ${toolName}...`
}

const PHASE_ACTIONS: Record<string, { label: string; pendingLabel: string }> = {
  strategy: { label: 'Extract ICP', pendingLabel: 'Extracting...' },
  contacts: { label: 'Select Contacts', pendingLabel: 'Selecting...' },
  messages: { label: 'Generate Messages', pendingLabel: 'Generating...' },
  campaign: { label: 'Launch Campaign', pendingLabel: 'Launching...' },
}

// ---------------------------------------------------------------------------
// PlaybookPage
// ---------------------------------------------------------------------------

export function PlaybookPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { phase: urlPhase } = useParams<{ phase: string }>()

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
  const [activeToolName, setActiveToolName] = useState<string | null>(null)

  // Refs for debounced auto-save
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latestContentRef = useRef<string | null>(null)
  // Track what was last saved to avoid saving identical content (fixes blink bug)
  const lastSavedContentRef = useRef<string | null>(null)

  // Track document version for optimistic locking
  const versionRef = useRef(0)

  // Determine view phase from URL or doc's phase
  const docPhase = docQuery.data?.phase || 'strategy'
  const viewPhase: PhaseKey = isValidPhase(urlPhase)
    ? urlPhase
    : isValidPhase(docPhase) ? docPhase : 'strategy'

  // Seed lastSavedContentRef with server content on first load
  useEffect(() => {
    if (docQuery.data?.content && lastSavedContentRef.current === null) {
      lastSavedContentRef.current = docQuery.data.content
    }
  }, [docQuery.data?.content])

  // Keep version ref in sync with server data
  useEffect(() => {
    if (docQuery.data) {
      versionRef.current = docQuery.data.version
    }
  }, [docQuery.data])

  // Poll for content when document has enrichment_id but empty content
  // (race condition: research completed before template was seeded)
  const docRefetch = docQuery.refetch
  useEffect(() => {
    if (!docQuery.data) return
    const hasEnrichment = !!docQuery.data.enrichment_id
    const hasContent = !!(docQuery.data.content && docQuery.data.content.trim().length > 0)
    if (hasEnrichment && !hasContent && !isDirty) {
      const interval = setInterval(() => {
        docRefetch()
      }, 2000)
      return () => clearInterval(interval)
    }
  }, [docQuery.data, isDirty, docRefetch])

  // Derive localContent: user edits take priority over server data
  const localContent = isDirty
    ? editedContent
    : (docQuery.data?.content ?? null)

  // ---------------------------------------------------------------------------
  // Auto-save logic
  // ---------------------------------------------------------------------------

  const performSave = useCallback(async (content: string) => {
    // Skip if content hasn't changed since last save
    if (content === lastSavedContentRef.current) {
      setIsDirty(false)
      return
    }
    setSaveStatus('saving')
    try {
      await saveMutation.mutateAsync({ content })
      lastSavedContentRef.current = content
      setIsDirty(false)
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
  // Phase navigation
  // ---------------------------------------------------------------------------

  const handlePhaseNavigate = useCallback(
    (phase: string) => {
      // Build the current namespace prefix from URL
      const pathParts = window.location.pathname.split('/')
      // URL pattern: /:namespace/playbook/:phase
      const namespace = pathParts[1]
      navigate(`/${namespace}/playbook/${phase}`)
    },
    [navigate],
  )

  // ---------------------------------------------------------------------------
  // Editor handlers
  // ---------------------------------------------------------------------------

  const handleEditorUpdate = useCallback((content: string) => {
    // Skip if content matches what's already saved (e.g. Tiptap init firing onUpdate)
    if (content === lastSavedContentRef.current) return

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

      sse.startStream(url, { message: text, phase: viewPhase }, headers, {
        onChunk: (chunk) => {
          setStreamingText((prev) => prev + chunk)
        },
        onDone: (_messageId, toolCalls) => {
          setStreamingText('')
          setOptimisticMessages([])
          setActiveToolName(null)
          // Refetch chat history from server to get persisted messages
          chatQuery.refetch()

          // If any tool calls modified data, invalidate relevant queries
          if (toolCalls && toolCalls.length > 0) {
            // Future tool specs define which query keys to invalidate.
            // For now, invalidate playbook data on any successful write tool.
            const hasWrites = toolCalls.some(
              (tc) => tc.status === 'success' && !tc.tool_name.startsWith('get_'),
            )
            if (hasWrites) {
              queryClient.invalidateQueries({ queryKey: ['playbook'], exact: true })
            }
          }
        },
        onError: (error) => {
          setStreamingText('')
          setOptimisticMessages([])
          setActiveToolName(null)
          toast(error.message || 'Chat error', 'error')
        },
        onToolStart: (toolName) => {
          setActiveToolName(getToolDisplayName(toolName))
        },
        onToolResult: () => {
          // activeToolName is cleared by onDone — no need to clear here
          // (clearing here caused a flash of empty state between tool calls)
        },
      })
    },
    [sse, chatQuery, toast, viewPhase, queryClient],
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

  const phaseAction = PHASE_ACTIONS[viewPhase] || PHASE_ACTIONS.strategy

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Top bar */}
      <div className="flex items-center gap-3 mb-2 flex-shrink-0">
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
          {/* Phase-specific action button */}
          {viewPhase === 'strategy' ? (
            <button
              onClick={handleExtract}
              disabled={extractMutation.isPending || saveStatus === 'saving'}
              title={saveStatus === 'saving' ? 'Waiting for save...' : 'Extract structured data from strategy'}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors bg-transparent border cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed border-accent-cyan/30 text-accent-cyan hover:bg-accent-cyan/10"
            >
              <ExtractIcon />
              {extractMutation.isPending ? phaseAction.pendingLabel : phaseAction.label}
            </button>
          ) : (
            <button
              disabled
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors bg-transparent border cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed border-accent-cyan/30 text-accent-cyan"
            >
              {phaseAction.label}
            </button>
          )}
        </div>
      </div>

      {/* Phase indicator */}
      <PhaseIndicator
        current={viewPhase}
        unlocked={docPhase}
        onNavigate={handlePhaseNavigate}
      />

      {/* Split layout */}
      <div className="flex gap-4 flex-1 min-h-0">
        {/* Left: Phase-specific panel */}
        <div className="flex-[3] min-w-0 flex flex-col min-h-0">
          <PhasePanel
            phase={viewPhase}
            content={localContent}
            onEditorUpdate={handleEditorUpdate}
            editable={saveStatus !== 'saving'}
          />
        </div>

        {/* Right: Chat */}
        <div className="flex-[2] min-w-0 flex flex-col min-h-0">
          <PlaybookChat
            messages={allMessages}
            onSendMessage={handleSendMessage}
            isStreaming={sse.isStreaming}
            streamingText={streamingText}
            placeholder={PHASE_PLACEHOLDERS[viewPhase]}
            activeToolName={activeToolName}
          />
        </div>
      </div>
    </div>
  )
}
