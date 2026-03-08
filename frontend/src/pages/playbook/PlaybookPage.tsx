/**
 * PlaybookPage -- full-width GTM strategy editor.
 *
 * Phase-specific content (StrategyEditor for strategy, placeholders for others).
 * Chat is provided by the unified ChatSidebar in AppShell.
 *
 * Shows onboarding flow for first-time visitors (no enrichment data yet).
 *
 * Wires together: usePlaybookDocument, useSavePlaybook,
 * useExtractStrategy, PhasePanel, PlaybookOnboarding.
 * Chat is handled by ChatSidebar in AppShell (app-level).
 *
 * WRITE feature: handles document_changed signals from AI tool calls,
 * refreshes editor content, and provides undo for AI edits.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { PHASE_ORDER, type PhaseKey } from '../../components/playbook/PhaseIndicator'
import { PhasePanel } from '../../components/playbook/PhasePanel'
import { PlaybookOnboarding, type OnboardingPayload } from '../../components/playbook/PlaybookOnboarding'
import { TemplateSelector } from '../../components/playbook/TemplateSelector'
import { IcpTiersTab } from '../../components/playbook/IcpTiersTab'
import { BuyerPersonasTab } from '../../components/playbook/BuyerPersonasTab'
import { VersionBrowser } from '../../components/playbook/VersionBrowser'
import {
  usePlaybookDocument,
  useSavePlaybook,
  useUndoAIEdit,
  useTriggerResearch,
  useResearchStatus,
} from '../../api/queries/usePlaybook'
import { useApplyStrategyTemplate } from '../../api/queries/useStrategyTemplates'
import { useChatContext } from '../../providers/ChatProvider'
import { useToast } from '../../components/ui/Toast'

// ---------------------------------------------------------------------------
// Auto-save status type
// ---------------------------------------------------------------------------

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isValidPhase(phase: string | undefined): phase is PhaseKey {
  return PHASE_ORDER.includes(phase as PhaseKey)
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

// BL-201: ExtractIcon removed — Extract ICP button no longer exists

function UndoIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7h6a4 4 0 0 1 0 8H9" />
      <path d="M3 7l3-3M3 7l3 3" />
    </svg>
  )
}

function SaveTemplateIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12.67 14H3.33A1.33 1.33 0 0 1 2 12.67V3.33A1.33 1.33 0 0 1 3.33 2h7.34L14 5.33v7.34A1.33 1.33 0 0 1 12.67 14Z" />
      <path d="M11.33 14V9.33H4.67V14M4.67 2v3.33h5.33" />
    </svg>
  )
}

function HistoryIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1.5 8a6.5 6.5 0 1 1 1.28 3.88" />
      <path d="M1 4.5v4h4" />
      <path d="M8 4.5V8l2.5 1.5" />
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
  const { namespace, phase: urlPhase } = useParams<{ namespace: string; phase: string }>()

  // Chat state from provider (persists across navigation)
  const {
    isStreaming,
    sendMessage,
    documentChanged,
    clearDocumentChanged,
    toolCalls,
    sectionStreamingText,
    isSectionStreaming,
    streamingSection,
    isThinking,
    activeToolName,
    analysisStreamingText,
    isAnalysisStreaming,
    analysisSuggestions,
    currentFinding,
    messageFindings,
    messageQuickActions,
    handleQuickAction,
  } = useChatContext()

  // Server state
  const docQuery = usePlaybookDocument()
  const saveMutation = useSavePlaybook()
  // BL-201: extractMutation removed — extraction is now continuous
  // advancePhaseMutation removed — phase actions now handled via AI chat tools
  const undoMutation = useUndoAIEdit()
  const triggerResearch = useTriggerResearch()

  // Template application (BL-138)
  const applyTemplateMutation = useApplyStrategyTemplate({
    onError: () => {
      toast('Template could not be applied. The AI will generate your strategy instead.', 'error')
    },
  })
  const [showTemplateSelector, setShowTemplateSelector] = useState(false)

  // Strategy sub-tab state (BL-198, BL-199)
  const [activeStrategyTab, setActiveStrategyTab] = useState<'strategy' | 'tiers' | 'personas'>('strategy')

  // Local state
  const [editedContent, setEditedContent] = useState<string | null>(null)
  const [isDirty, setIsDirty] = useState(false)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [skipped, setSkipped] = useState(false)
  const [researchTriggered, setResearchTriggered] = useState(false)

  // Poll research status once research has been triggered
  const researchQuery = useResearchStatus(researchTriggered)
  const [showUndoConfirm, setShowUndoConfirm] = useState(false)
  // BL-201: extractionResult state removed — extraction is now continuous
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [showVersionBrowser, setShowVersionBrowser] = useState(false)
  const [showSaveTemplate, setShowSaveTemplate] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const [templateDescription, setTemplateDescription] = useState('')
  const [triageSynced, setTriageSynced] = useState(false)

  // Refs for debounced auto-save
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latestContentRef = useRef<string | null>(null)
  // Track what was last saved to avoid saving identical content (fixes blink bug)
  const lastSavedContentRef = useRef<string | null>(null)
  // Ref to allow unmount cleanup to call the latest saveMutation.mutate
  const saveMutationRef = useRef(saveMutation)
  useEffect(() => {
    saveMutationRef.current = saveMutation
  }, [saveMutation])

  // Track document version for optimistic locking
  const versionRef = useRef(0)

  // Determine view phase from URL — default to strategy when no phase in URL.
  // The document's phase tracks workflow progress but should NOT override the
  // landing view. Users always land on the strategy editor unless they
  // explicitly navigate to another phase via URL (e.g. /playbook/contacts).
  const viewPhase: PhaseKey = isValidPhase(urlPhase) ? urlPhase : 'strategy'

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

  // No polling needed for template seeding — the document starts blank
  // and is populated incrementally by AI via section_update SSE events.

  // ---------------------------------------------------------------------------
  // Auto-refresh when research completes or fails
  // ---------------------------------------------------------------------------

  const prevResearchStatus = useRef<string | null>(null)
  useEffect(() => {
    const status = researchQuery.data?.status
    if (!status) return
    if (prevResearchStatus.current === 'in_progress' && status === 'completed') {
      // Research just finished -- refresh the document to pick up enrichment data
      queryClient.invalidateQueries({ queryKey: ['playbook', namespace] })
      toast('Company research completed', 'info')
    }
    if (prevResearchStatus.current === 'in_progress' && status === 'failed') {
      // Research failed or timed out -- still refresh (may have partial data)
      queryClient.invalidateQueries({ queryKey: ['playbook'] })
      toast('Company research could not complete. The AI can still help with your strategy.', 'error')
    }
    prevResearchStatus.current = status
  }, [researchQuery.data?.status, queryClient, toast, namespace])

  // ---------------------------------------------------------------------------
  // Poll chat during research to show progress tool cards (BL-191)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const isInProgress = researchQuery.data?.status === 'in_progress'
    if (!isInProgress) return

    const interval = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ['playbook', 'chat'] })
    }, 3000)

    return () => clearInterval(interval)
  }, [researchQuery.data?.status, queryClient])

  // ---------------------------------------------------------------------------
  // Handle AI document changes (from ChatProvider)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!documentChanged?.changed) return

    if (saveStatus !== 'saved' && isDirty) {
      // User has unsaved changes -- don't auto-replace, show toast
      toast(
        documentChanged.summary ?? 'Strategy updated by AI',
        'info',
      )
    } else {
      // No unsaved changes -- safe to auto-refresh the editor
      // Update lastSavedContentRef so the debounced save sees no diff and skips
      queryClient.invalidateQueries({ queryKey: ['playbook', namespace], exact: true }).then(() => {
        // After refetch, update the saved content ref to match server state
        const newContent = queryClient.getQueryData<{ content?: string }>(['playbook', namespace])
        if (newContent?.content) {
          lastSavedContentRef.current = newContent.content
          setEditedContent(null)
          setIsDirty(false)
        }
      })

      // Show toast summarizing changes
      if (documentChanged.summary) {
        toast(documentChanged.summary, 'info')
      }
    }

    clearDocumentChanged()
  }, [documentChanged, saveStatus, isDirty, queryClient, toast, clearDocumentChanged, namespace])

  // ---------------------------------------------------------------------------
  // Per-section save progress indicator (BL-151)
  // Show a brief toast each time an AI strategy tool call completes
  // ---------------------------------------------------------------------------

  const processedToolCallsRef = useRef(new Set<string>())
  useEffect(() => {
    const STRATEGY_TOOLS = new Set([
      'update_strategy_section',
      'append_to_section',
      'set_extracted_field',
    ])
    for (const tc of toolCalls) {
      if (
        tc.status === 'success' &&
        STRATEGY_TOOLS.has(tc.tool_name) &&
        !processedToolCallsRef.current.has(tc.tool_call_id)
      ) {
        processedToolCallsRef.current.add(tc.tool_call_id)
        const section = (tc.input?.section_name as string) || (tc.input?.field as string) || ''
        const label = section
          ? `Section saved: ${section.replace(/_/g, ' ')}`
          : 'Section saved'
        toast(label, 'info')
      }
    }
  }, [toolCalls, toast])

  // Clear processed set when tool calls reset (new message)
  useEffect(() => {
    if (toolCalls.length === 0) {
      processedToolCallsRef.current.clear()
    }
  }, [toolCalls.length])

  // Derive localContent: user edits take priority over server data
  const localContent = isDirty
    ? editedContent
    : (docQuery.data?.content ?? null)

  // Derive whether undo is available
  const hasUndoableEdits = docQuery.data?.has_ai_edits ?? false

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
      const saved = await saveMutation.mutateAsync({ content })
      lastSavedContentRef.current = content
      // Update query cache so localContent stays in sync when isDirty goes false
      if (saved) {
        queryClient.setQueryData(['playbook', namespace], saved)
      }
      setIsDirty(false)
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus((s) => s === 'saved' ? 'idle' : s), 2000)
    } catch {
      setSaveStatus('error')
      toast('Failed to save', 'error')
    }
  }, [saveMutation, toast, queryClient, namespace])

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

  // Flush pending save on unmount (e.g. when navigating away)
  // instead of just clearing the timer — otherwise edits are lost
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
        debounceTimerRef.current = null
      }
      // Fire-and-forget: flush any unsaved content via ref (avoids stale closure)
      const pending = latestContentRef.current
      if (pending !== null && pending !== lastSavedContentRef.current) {
        saveMutationRef.current.mutate({ content: pending })
        lastSavedContentRef.current = pending
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

  // BL-201: Extract handler removed — extraction is now continuous via AI tools

  // ---------------------------------------------------------------------------
  // Undo AI edit handler
  // ---------------------------------------------------------------------------

  const handleUndoClick = useCallback(() => {
    setShowUndoConfirm(true)
  }, [])

  const handleUndoConfirmed = useCallback(async () => {
    setShowUndoConfirm(false)
    try {
      await undoMutation.mutateAsync()
      // Refetch doc after undo and update refs
      const result = await docQuery.refetch()
      if (result.data?.content) {
        lastSavedContentRef.current = result.data.content
        setEditedContent(null)
        setIsDirty(false)
      }
      toast('Reverted to previous version', 'success')
    } catch {
      toast('Undo failed', 'error')
    }
  }, [undoMutation, docQuery, toast])

  // ---------------------------------------------------------------------------
  // Onboarding: generate strategy via AI chat
  // ---------------------------------------------------------------------------

  const handleOnboardGenerate = useCallback(
    async (payload: OnboardingPayload) => {
      const primaryDomain = payload.domains[0] || ''

      // Save description as objective to the document
      try {
        await saveMutation.mutateAsync({ objective: payload.description })
      } catch {
        // Objective save failed -- continue anyway, AI will still work
      }

      // Fire research in parallel (non-blocking) -- enriches company data
      if (primaryDomain) {
        triggerResearch.mutate(
          {
            domains: payload.domains,
            primary_domain: primaryDomain,
            challenge_type: payload.challenge_type,
          },
          {
            onSuccess: () => {
              setResearchTriggered(true)
            },
            onError: () => {
              // Research failed -- non-fatal, AI still works without enrichment
            },
          },
        )
      }

      // Build a crafted prompt for the AI to generate the strategy
      const challengeLabel = payload.challenge_type
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase())

      const parts = [
        `Generate a complete GTM strategy playbook for my company (${primaryDomain}).`,
        `GTM objective: ${payload.description}.`,
        `Primary challenge: ${challengeLabel}.`,
      ]
      if (payload.domains.length > 1) {
        parts.push(
          `Key competitors/related domains: ${payload.domains.slice(1).join(', ')}.`,
        )
      }
      parts.push(
        'Use the company research data provided in your context to write the strategy. ' +
          'Execute these steps NOW using your tools (do not just describe what you would do — actually call the tools): ' +
          '1) Call get_strategy_document to see current state. ' +
          '2) Call update_strategy_section for EACH of the 7 strategy sections with specific, researched content. ' +
          'If the research data in your context is thin, use web_search to fill gaps. ' +
          'Complete all sections in this turn. Start now.',
      )

      sendMessage(parts.join(' '))

      // Exit onboarding gate immediately -- the chat sidebar shows AI progress
      setSkipped(true)
    },
    [sendMessage, saveMutation, triggerResearch],
  )

  // ---------------------------------------------------------------------------
  // Template selection handler (BL-138)
  // ---------------------------------------------------------------------------

  const handleTemplateSelect = useCallback(
    async (templateId: string | null) => {
      if (!templateId) {
        // "Start fresh" — skip template, go to onboarding form
        setShowTemplateSelector(false)
        return
      }
      try {
        await applyTemplateMutation.mutateAsync(templateId)
        // Template applied — skip onboarding entirely, show the editor
        setSkipped(true)
        setShowTemplateSelector(false)
      } catch {
        // Error toast is handled by the mutation's onError callback.
        // Don't block the user — close the template selector and proceed.
        setShowTemplateSelector(false)
      }
    },
    [applyTemplateMutation],
  )

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
  // Onboarding gate -- show inline if doc is blank and user hasn't skipped
  // ---------------------------------------------------------------------------

  const docContent = docQuery.data?.content || ''
  const needsOnboarding = !!(docQuery.data && !docContent.trim() && !docQuery.data?.objective && !skipped)

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  // BL-201: phaseAction variable removed — Extract ICP button is gone

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden">
      {/* Top bar */}
      <div className="flex items-center gap-3 mb-2 flex-shrink-0">
        <h1 className="font-title text-[1.3rem] font-semibold tracking-tight">
          GTM Strategy
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

        {/* Research progress is now shown via tool cards in chat (BL-194) */}

        <div className="ml-auto flex items-center gap-2">
          {/* Version History */}
          {viewPhase === 'strategy' && docQuery.data?.id && (
            <button
              onClick={() => setShowVersionBrowser(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-border text-text-muted hover:text-text hover:bg-surface-alt transition-colors bg-transparent cursor-pointer"
              title="View version history"
            >
              <HistoryIcon />
              History
            </button>
          )}

          {/* Save as Template */}
          {viewPhase === 'strategy' && docContent.trim() && (
            <button
              onClick={() => setShowSaveTemplate(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-border text-text-muted hover:text-text hover:bg-surface-alt transition-colors bg-transparent cursor-pointer"
              title="Save current strategy as a reusable template"
            >
              <SaveTemplateIcon />
              Save as Template
            </button>
          )}


          {/* Undo AI edit button */}
          {hasUndoableEdits && (
            <button
              onClick={handleUndoClick}
              disabled={undoMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-warning/30 text-warning hover:bg-warning/10 transition-colors bg-transparent cursor-pointer disabled:opacity-40"
            >
              <UndoIcon />
              {undoMutation.isPending ? 'Reverting...' : 'Undo AI edit'}
            </button>
          )}

          {/* BL-201: Extract ICP button removed — extraction is now continuous */}
        </div>
      </div>

      {/* Strategy sub-tabs (BL-198, BL-199) -- only in strategy phase */}
      {viewPhase === 'strategy' && !needsOnboarding && (
        <div className="flex items-center gap-1 mb-2 flex-shrink-0 border-b border-border">
          {([
            { key: 'strategy' as const, label: 'Strategy Overview' },
            { key: 'tiers' as const, label: 'ICP Tiers' },
            { key: 'personas' as const, label: 'Buyer Personas' },
          ]).map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setActiveStrategyTab(key)}
              className={`px-3 py-2 text-xs font-medium transition-colors bg-transparent cursor-pointer border-0 border-b-2 -mb-px ${
                activeStrategyTab === key
                  ? 'border-accent text-accent'
                  : 'border-transparent text-text-muted hover:text-text hover:border-border-solid'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Undo confirmation dialog */}
      {showUndoConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-surface border border-border-solid rounded-lg shadow-lg p-6 max-w-sm mx-4">
            <h3 className="text-sm font-semibold mb-2">Undo AI edit?</h3>
            <p className="text-xs text-text-muted mb-4">
              This will revert the strategy document to its state before the last AI edit.
              Any manual changes made since then will be lost.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowUndoConfirm(false)}
                className="px-3 py-1.5 text-xs font-medium rounded-md border border-border-solid text-text-muted hover:bg-surface-alt transition-colors bg-transparent cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleUndoConfirmed}
                className="px-3 py-1.5 text-xs font-medium rounded-md border border-warning/30 text-warning hover:bg-warning/10 transition-colors bg-transparent cursor-pointer"
              >
                Undo
              </button>
            </div>
          </div>
        </div>
      )}

      {/* BL-201: Extraction side panel removed — extraction is now continuous */}

      {/* Phase content -- full width (chat is in the sidebar) */}
      <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
        {needsOnboarding && showTemplateSelector ? (
          <div className="flex items-center justify-center h-full">
            <TemplateSelector
              onSelect={handleTemplateSelect}
              onBack={() => setShowTemplateSelector(false)}
              isApplying={applyTemplateMutation.isPending}
            />
          </div>
        ) : needsOnboarding ? (
          <div className="flex-1 overflow-y-auto">
            <PlaybookOnboarding
              onSkip={() => setSkipped(true)}
              onGenerate={handleOnboardGenerate}
              isGenerating={isStreaming}
              onBrowseTemplates={() => setShowTemplateSelector(true)}
            />
          </div>
        ) : viewPhase === 'strategy' && activeStrategyTab === 'tiers' ? (
          <IcpTiersTab />
        ) : viewPhase === 'strategy' && activeStrategyTab === 'personas' ? (
          <BuyerPersonasTab />
        ) : (
          <PhasePanel
            phase={viewPhase}
            content={localContent}
            onEditorUpdate={handleEditorUpdate}
            editable={saveStatus !== 'saving'}
            extractedData={docQuery.data?.extracted_data}
            playbookSelections={docQuery.data?.playbook_selections}
            playbookId={docQuery.data?.id}
            onPhaseAdvance={handlePhaseNavigate}
            sectionStreamingText={sectionStreamingText}
            isSectionStreaming={isSectionStreaming}
            streamingSection={streamingSection}
          />
        )}
      </div>

      {/* Version History panel (BL-1014) */}
      {docQuery.data?.id && (
        <VersionBrowser
          documentId={docQuery.data.id}
          open={showVersionBrowser}
          onClose={() => setShowVersionBrowser(false)}
        />
      )}
    </div>
  )
}

// BL-201: ExtractionSidePanel removed — extraction is now continuous via AI tools

// BL-201: ExtractionSidePanel, ExtractionSection, and ExtractionPills removed.
// ICP extraction is now continuous via AI tools (set_icp_tiers, set_buyer_personas)
// and structured data is displayed in the dedicated ICP Tiers and Buyer Personas tabs.
