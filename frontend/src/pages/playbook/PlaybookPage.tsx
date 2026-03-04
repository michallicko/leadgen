/**
 * PlaybookPage -- split-view editor + AI chat for ICP strategy.
 *
 * Left panel (~60%): Phase-specific content (StrategyEditor for strategy, placeholders for others)
 * Right panel (~40%): AI chat — uses ChatProvider for persistent state
 *
 * Shows onboarding flow for first-time visitors (no enrichment data yet).
 *
 * Wires together: usePlaybookDocument, useSavePlaybook,
 * useExtractStrategy, PhaseIndicator, PhasePanel, PlaybookChat, PlaybookOnboarding.
 * Chat state is provided by ChatProvider (app-level).
 *
 * WRITE feature: handles document_changed signals from AI tool calls,
 * refreshes editor content, and provides undo for AI edits.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { PhaseIndicator, PHASE_ORDER, type PhaseKey } from '../../components/playbook/PhaseIndicator'
import { PhasePanel } from '../../components/playbook/PhasePanel'
import { PlaybookChat } from '../../components/playbook/PlaybookChat'
import { PlaybookOnboarding, type OnboardingPayload } from '../../components/playbook/PlaybookOnboarding'
import { TemplateSelector } from '../../components/playbook/TemplateSelector'
import {
  usePlaybookDocument,
  useSavePlaybook,
  useExtractStrategy,
  useAdvancePhase,
  useUndoAIEdit,
  useTriggerResearch,
  useResearchStatus,
} from '../../api/queries/usePlaybook'
import { useCreateStrategyTemplate, useApplyStrategyTemplate } from '../../api/queries/useStrategyTemplates'
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

function ExtractIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 2v8M5 7l3 3 3-3" />
      <path d="M2 11v2a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-2" />
    </svg>
  )
}

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
    messages,
    isStreaming,
    streamingText,
    isLoading: chatLoading,
    sendMessage,
    chatInputRef,
    documentChanged,
    clearDocumentChanged,
    toolCalls,
    isThinking,
    activeToolName,
    analysisStreamingText,
    isAnalysisStreaming,
    analysisSuggestions,
  } = useChatContext()

  // Server state
  const docQuery = usePlaybookDocument()
  const saveMutation = useSavePlaybook()
  const extractMutation = useExtractStrategy()
  const advancePhaseMutation = useAdvancePhase()
  const undoMutation = useUndoAIEdit()
  const createTemplateMutation = useCreateStrategyTemplate()
  const triggerResearch = useTriggerResearch()

  // Template application (BL-138)
  const applyTemplateMutation = useApplyStrategyTemplate({
    onError: () => {
      toast('Template could not be applied. The AI will generate your strategy instead.', 'error')
    },
  })
  const [showTemplateSelector, setShowTemplateSelector] = useState(false)

  // Local state
  const [editedContent, setEditedContent] = useState<string | null>(null)
  const [isDirty, setIsDirty] = useState(false)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [skipped, setSkipped] = useState(false)
  const [researchTriggered, setResearchTriggered] = useState(false)

  // Poll research status once research has been triggered
  const researchQuery = useResearchStatus(researchTriggered)
  const [showUndoConfirm, setShowUndoConfirm] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [showSaveTemplate, setShowSaveTemplate] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const [templateDescription, setTemplateDescription] = useState('')
  const [extractionResult, setExtractionResult] = useState<Record<string, unknown> | null>(null)
  const [triageSynced, setTriageSynced] = useState(false)

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
      const result = await extractMutation.mutateAsync()
      const extractedData = (result as Record<string, unknown>)?.extracted_data as Record<string, unknown> | undefined
      const synced = !!(result as Record<string, unknown>)?.triage_synced

      if (extractedData) {
        setExtractionResult(extractedData)
        setTriageSynced(synced)
        toast('ICP criteria extracted successfully', 'success')
      } else {
        toast('Strategy data extracted but no structured data found. Try adding more detail to your strategy.', 'info')
      }
    } catch {
      toast('Extraction failed. Please try again.', 'error')
    }
  }, [extractMutation, toast])

  const handleExtractionConfirm = useCallback(async () => {
    setExtractionResult(null)
    const hasIcp = extractionResult?.icp && typeof extractionResult.icp === 'object' && Object.keys(extractionResult.icp as object).length > 0
    if (hasIcp) {
      try {
        await advancePhaseMutation.mutateAsync({ phase: 'contacts' })
        toast('Moving to Contacts phase...', 'success')
        handlePhaseNavigate('contacts')
      } catch {
        toast('ICP extracted successfully', 'success')
      }
    } else {
      toast('Data extracted. Add ICP details to your strategy to unlock contact filtering.', 'info')
    }
  }, [extractionResult, advancePhaseMutation, toast, handlePhaseNavigate])

  const handleExtractionDismiss = useCallback(() => {
    setExtractionResult(null)
  }, [])

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
        'Execute these steps NOW using your tools (do not just describe what you would do — actually call the tools): ' +
          `1) Call web_search to research "${primaryDomain}" — search for company overview, products, market, and competitors. ` +
          '2) Call web_search again for industry trends and competitive landscape. ' +
          '3) Call get_strategy_document to see current state. ' +
          '4) Call update_strategy_section for EACH of the 9 strategy sections with specific, researched content. ' +
          'Complete all sections in this turn. Start now.',
      )

      sendMessage(parts.join(' '))

      // Exit onboarding gate immediately -- the chat panel is visible in the
      // main split view so the user can follow the AI's progress there
      setSkipped(true)
      setShowSuggestions(true)
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
  // Save as Template handler
  // ---------------------------------------------------------------------------

  const handleSaveAsTemplate = useCallback(async () => {
    if (!templateName.trim()) return
    try {
      await createTemplateMutation.mutateAsync({
        name: templateName.trim(),
        description: templateDescription.trim() || undefined,
      })
      setShowSaveTemplate(false)
      setTemplateName('')
      setTemplateDescription('')
      toast('Strategy saved as template', 'success')
    } catch {
      toast('Failed to save template', 'error')
    }
  }, [templateName, templateDescription, createTemplateMutation, toast])

  // Wrap sendMessage to dismiss suggestions on first user follow-up
  const handleSendWithSuggestionDismiss = useCallback(
    (text: string) => {
      setShowSuggestions(false)
      sendMessage(text)
    },
    [sendMessage],
  )

  const ONBOARDING_SUGGESTIONS = [
    'Refine my ICP criteria',
    'Add more buyer personas',
    'Strengthen the value proposition',
    'Suggest outreach channels',
  ]

  // Dynamic suggestions from proactive analysis take priority over static ones
  const activeSuggestions = analysisSuggestions.length > 0
    ? analysisSuggestions
    : (showSuggestions ? ONBOARDING_SUGGESTIONS : [])

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
  const needsOnboarding = !!(docQuery.data && !docContent.trim() && !skipped)

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

        {/* Research status indicator */}
        {researchTriggered && researchQuery.data?.status === 'in_progress' && (
          <div className="flex items-center gap-1.5 ml-1">
            <span className="w-3 h-3 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
            <span className="text-xs text-accent-cyan font-medium">
              Researching...
            </span>
          </div>
        )}
        {researchTriggered && researchQuery.data?.status === 'failed' && (
          <div className="flex items-center gap-1.5 ml-1">
            <span className="text-xs text-text-muted">
              Research incomplete
            </span>
          </div>
        )}

        <div className="ml-auto flex items-center gap-2">
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

          {/* Phase-specific action button (strategy only -- other phases have panel-level actions) */}
          {viewPhase === 'strategy' && (
            <button
              onClick={handleExtract}
              disabled={extractMutation.isPending || saveStatus === 'saving'}
              title={saveStatus === 'saving' ? 'Waiting for save...' : 'Extract structured data from strategy'}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors bg-transparent border cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed border-accent-cyan/30 text-accent-cyan hover:bg-accent-cyan/10"
            >
              <ExtractIcon />
              {extractMutation.isPending ? phaseAction.pendingLabel : phaseAction.label}
            </button>
          )}
        </div>
      </div>

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

      {/* Save as Template dialog */}
      {showSaveTemplate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-surface border border-border-solid rounded-lg shadow-lg p-6 max-w-sm mx-4 w-full">
            <h3 className="text-sm font-semibold mb-3">Save as Template</h3>
            <div className="space-y-3 mb-4">
              <div>
                <label htmlFor="tpl-name" className="block text-xs font-medium text-text mb-1">
                  Template name
                </label>
                <input
                  id="tpl-name"
                  type="text"
                  value={templateName}
                  onChange={(e) => setTemplateName(e.target.value)}
                  placeholder="e.g., My SaaS GTM Framework"
                  className="w-full px-3 py-1.5 text-sm rounded-md border border-border-solid bg-surface-alt text-text placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-accent/40"
                />
              </div>
              <div>
                <label htmlFor="tpl-desc" className="block text-xs font-medium text-text mb-1">
                  Description <span className="text-text-dim font-normal">(optional)</span>
                </label>
                <textarea
                  id="tpl-desc"
                  value={templateDescription}
                  onChange={(e) => setTemplateDescription(e.target.value)}
                  placeholder="Brief description of this strategy framework"
                  rows={2}
                  className="w-full px-3 py-1.5 text-sm rounded-md border border-border-solid bg-surface-alt text-text placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-accent/40 resize-none"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setShowSaveTemplate(false); setTemplateName(''); setTemplateDescription('') }}
                className="px-3 py-1.5 text-xs font-medium rounded-md border border-border-solid text-text-muted hover:bg-surface-alt transition-colors bg-transparent cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveAsTemplate}
                disabled={!templateName.trim() || createTemplateMutation.isPending}
                className="px-3 py-1.5 text-xs font-medium rounded-md bg-accent text-white hover:bg-accent-hover transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {createTemplateMutation.isPending ? 'Saving...' : 'Save Template'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Extraction summary side panel */}
      {extractionResult && (
        <ExtractionSidePanel
          data={extractionResult}
          triageSynced={triageSynced}
          onConfirm={handleExtractionConfirm}
          onDismiss={handleExtractionDismiss}
        />
      )}

      {/* Phase indicator */}
      <PhaseIndicator
        current={viewPhase}
        unlocked={docPhase}
        onNavigate={handlePhaseNavigate}
      />

      {/* Split layout */}
      <div className="flex gap-4 flex-1 min-h-0">
        {/* Left: Phase-specific panel OR onboarding box */}
        <div className="flex-[3] min-w-0 flex flex-col min-h-0">
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
            />
          )}
        </div>

        {/* Right: Inline Chat (uses ChatProvider state) */}
        <div className="flex-[2] min-w-0 flex flex-col min-h-0">
          <PlaybookChat
            messages={messages}
            onSendMessage={handleSendWithSuggestionDismiss}
            isStreaming={isStreaming || isAnalysisStreaming}
            streamingText={isAnalysisStreaming ? analysisStreamingText : streamingText}
            placeholder={PHASE_PLACEHOLDERS[viewPhase]}
            activeToolName={isAnalysisStreaming ? 'Analyzing strategy...' : activeToolName}
            isLoading={chatLoading}
            inputRef={chatInputRef}
            toolCalls={toolCalls}
            isThinking={isThinking}
            suggestions={activeSuggestions}
          />
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Extraction Side Panel
// ---------------------------------------------------------------------------

interface ExtractionSidePanelProps {
  data: Record<string, unknown>
  triageSynced?: boolean
  onConfirm: () => void
  onDismiss: () => void
}

function ExtractionSidePanel({ data, triageSynced, onConfirm, onDismiss }: ExtractionSidePanelProps) {
  const icp = data.icp as Record<string, unknown> | undefined
  const personas = data.personas as Array<Record<string, unknown>> | undefined
  const messaging = data.messaging as Record<string, unknown> | undefined
  const channels = data.channels as Record<string, unknown> | undefined

  const industries = (icp?.industries as string[]) ?? []
  const geographies = (icp?.geographies as string[]) ?? []
  const techSignals = (icp?.tech_signals as string[]) ?? []
  const triggers = (icp?.triggers as string[]) ?? []
  const disqualifiers = (icp?.disqualifiers as string[]) ?? []
  const companySize = icp?.company_size as { min?: number; max?: number } | undefined

  const titlePatterns = personas?.flatMap((p) => (p.title_patterns as string[]) ?? []) ?? []
  const themes = (messaging?.themes as string[]) ?? []
  const primaryChannel = (channels?.primary as string) ?? ''

  const hasIcp = industries.length > 0 || geographies.length > 0 || titlePatterns.length > 0

  // Slide-in animation state
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    requestAnimationFrame(() => setVisible(true))
  }, [])

  // Auto-advance countdown when ICP data is present
  const [countdown, setCountdown] = useState(hasIcp ? 5 : 0)

  useEffect(() => {
    if (!hasIcp) return
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer)
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [hasIcp])

  // Trigger onConfirm when countdown reaches 0
  const onConfirmRef = useRef(onConfirm)
  useEffect(() => {
    onConfirmRef.current = onConfirm
  }, [onConfirm])
  useEffect(() => {
    if (hasIcp && countdown === 0) {
      onConfirmRef.current()
    }
  }, [hasIcp, countdown])

  // Cancel countdown when user interacts
  const cancelCountdown = useCallback(() => {
    setCountdown(-1) // -1 = cancelled, won't trigger auto-advance
  }, [])

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      onClick={(e) => { if (e.target === e.currentTarget) { cancelCountdown(); onDismiss() } }}
    >
      {/* Translucent backdrop -- lets strategy peek through */}
      <div className="absolute inset-0 bg-black/20" />

      {/* Side panel */}
      <div
        className={`relative w-full max-w-md h-full bg-surface border-l border-accent-cyan/30 shadow-xl shadow-black/20 flex flex-col transition-transform duration-300 ease-out ${visible ? 'translate-x-0' : 'translate-x-full'}`}
      >
        {/* Header -- cyan accent for AI action */}
        <div className="px-5 pt-5 pb-3 flex items-center gap-3 border-b border-accent-cyan/20">
          <div className="w-8 h-8 rounded-lg bg-accent-cyan/10 flex items-center justify-center flex-shrink-0">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" className="text-accent-cyan">
              <path d="M4 9l3.5 3.5 6.5-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-text">Extraction Complete</h3>
            <p className="text-xs text-text-muted">
              {hasIcp
                ? 'Your ICP criteria have been extracted from the strategy.'
                : 'Basic data extracted. Add ICP details for better contact filtering.'}
            </p>
          </div>
          <button
            onClick={() => { cancelCountdown(); onDismiss() }}
            className="w-7 h-7 flex items-center justify-center rounded-md text-text-dim hover:text-text hover:bg-surface-alt transition-colors bg-transparent cursor-pointer border-0"
            title="Close"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M3 3l8 8M11 3l-8 8" />
            </svg>
          </button>
        </div>

        {/* Scrollable content */}
        <div className="px-5 py-4 overflow-y-auto flex-1 space-y-4">
          {/* ICP section */}
          {(industries.length > 0 || geographies.length > 0) && (
            <ExtractionSection title="Target Market">
              {industries.length > 0 && (
                <ExtractionPills label="Industries" values={industries} />
              )}
              {geographies.length > 0 && (
                <ExtractionPills label="Geographies" values={geographies} />
              )}
              {companySize && (companySize.min || companySize.max) ? (
                <ExtractionPills
                  label="Company Size"
                  values={[`${companySize.min || 0} - ${companySize.max || '1000+'} employees`]}
                />
              ) : null}
            </ExtractionSection>
          )}

          {/* Personas section */}
          {titlePatterns.length > 0 && (
            <ExtractionSection title="Target Roles">
              <ExtractionPills label="Job Titles" values={titlePatterns} />
            </ExtractionSection>
          )}

          {/* Signals section */}
          {(techSignals.length > 0 || triggers.length > 0 || disqualifiers.length > 0) && (
            <ExtractionSection title="Signals">
              {techSignals.length > 0 && (
                <ExtractionPills label="Tech Signals" values={techSignals} />
              )}
              {triggers.length > 0 && (
                <ExtractionPills label="Triggers" values={triggers} />
              )}
              {disqualifiers.length > 0 && (
                <ExtractionPills label="Disqualifiers" values={disqualifiers} variant="error" />
              )}
            </ExtractionSection>
          )}

          {/* Messaging section */}
          {(themes.length > 0 || primaryChannel) && (
            <ExtractionSection title="Messaging">
              {themes.length > 0 && (
                <ExtractionPills label="Themes" values={themes} />
              )}
              {primaryChannel && (
                <ExtractionPills label="Primary Channel" values={[primaryChannel]} />
              )}
            </ExtractionSection>
          )}

          {/* Triage sync notice */}
          {triageSynced && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-accent-cyan/5 border border-accent-cyan/20">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="text-accent-cyan flex-shrink-0">
                <path d="M7 1a6 6 0 100 12 6 6 0 000-12zM4.5 7l2 2 3.5-3.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span className="text-xs text-accent-cyan">
                Enrichment triage rules updated from your ICP criteria
              </span>
            </div>
          )}

          {/* Empty state if nothing meaningful extracted */}
          {!hasIcp && themes.length === 0 && techSignals.length === 0 && (
            <div className="text-center py-4">
              <p className="text-sm text-text-muted">
                No structured criteria could be extracted. Try adding more specific ICP details to your strategy document.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-border flex flex-col gap-3">
          <button
            onClick={() => { cancelCountdown(); onConfirm() }}
            className="w-full px-4 py-2.5 text-sm font-medium rounded-lg bg-accent-cyan text-white hover:brightness-110 transition-all cursor-pointer flex items-center justify-center gap-2"
          >
            {hasIcp ? 'Confirm & Continue' : 'OK'}
            {hasIcp && (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 7h8M8 3l3 4-3 4" />
              </svg>
            )}
          </button>
          <div className="flex items-center justify-between">
            <button
              onClick={() => { cancelCountdown(); onDismiss() }}
              className="px-3 py-1.5 text-xs font-medium rounded-md text-text-muted hover:text-text hover:bg-surface-alt transition-colors bg-transparent cursor-pointer border-0"
            >
              Stay on Strategy
            </button>
            {hasIcp && countdown > 0 && (
              <span className="text-xs text-text-dim">
                Advancing in {countdown}s...
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function ExtractionSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="text-xs font-semibold text-text-dim uppercase tracking-wider mb-2">{title}</h4>
      <div className="space-y-2">{children}</div>
    </div>
  )
}

function ExtractionPills({ label, values, variant }: { label: string; values: string[]; variant?: 'error' }) {
  const pillColor = variant === 'error'
    ? 'bg-error/10 border-error/20 text-error'
    : 'bg-accent-cyan/8 border-accent-cyan/20 text-text'
  return (
    <div>
      <span className="text-xs text-text-muted mb-1 block">{label}</span>
      <div className="flex flex-wrap gap-1.5">
        {values.map((v, i) => (
          <span
            key={i}
            className={`inline-flex px-2.5 py-1 text-xs rounded-full border ${pillColor}`}
          >
            {v}
          </span>
        ))}
      </div>
    </div>
  )
}
