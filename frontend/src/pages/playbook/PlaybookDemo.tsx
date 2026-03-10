/**
 * PlaybookDemo -- 2-minute automated demo loop showcasing the ideal
 * playbook interaction flow. Uses real UI components with a MockChatProvider
 * that simulates all interactions without any LLM calls.
 *
 * Sequence: Onboarding -> AI Research -> Strategy Streaming ->
 *           Phase Transition -> Sidebar Interaction -> Loop
 *
 * Route: /:namespace/playbook-demo
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  ChatContext,
  type ChatContextValue,
} from '../../providers/ChatProvider'
import { StrategyEditor } from '../../components/playbook/StrategyEditor'
import { PhaseIndicator } from '../../components/playbook/PhaseIndicator'
import { ChatMessages, type ChatMessage } from '../../components/chat/ChatMessages'
import { ChatInput } from '../../components/chat/ChatInput'
import type { ToolCallEvent } from '../../components/playbook/ToolCallCard'

// ---------------------------------------------------------------------------
// Demo content
// ---------------------------------------------------------------------------

const SECTION_1_TITLE = 'Executive Summary'
const SECTION_1 = `## Executive Summary

Acme Analytics is an AI-powered analytics platform targeting mid-market B2B companies (200-2000 employees). The platform differentiates through predictive insights and automated reporting, addressing the gap between enterprise BI tools and basic dashboards.

**Target Market Size:** $4.2B addressable, $840M serviceable
**Primary ICP:** VP of Operations at mid-market SaaS companies`

const SECTION_2_TITLE = 'Ideal Customer Profile'
const SECTION_2 = `## Ideal Customer Profile

### Tier 1 — Perfect Fit
- **Company:** B2B SaaS, 200-2000 employees, $10M-$100M ARR
- **Buyer:** VP Operations, Head of Analytics, COO
- **Pain:** Manual reporting consuming 20+ hours/week
- **Trigger:** Recent funding round, new C-suite hire, or scaling past 500 employees

### Tier 2 — Strong Fit
- **Company:** B2B Tech Services, 100-1000 employees
- **Buyer:** Director of Operations, CFO
- **Pain:** Spreadsheet-based forecasting breaking at scale`

const SECTION_3_TITLE = 'Outreach Strategy'
const SECTION_3 = `## Outreach Strategy

### Messaging Framework
**Hook:** "Your team spends 20+ hours per week on reports that could be automated"
**Value:** "Our customers reduce reporting time by 80% and catch revenue risks 3 weeks earlier"
**Proof:** "Dataflow Inc. went from 40 hours of manual reporting to 8 hours in their first month"

### Channel Sequence
1. LinkedIn connection request (personalized, mention shared context)
2. Day 3: LinkedIn message (value-first, no pitch)
3. Day 7: Email (case study, soft CTA)
4. Day 14: LinkedIn follow-up (insight share)`

// ---------------------------------------------------------------------------
// Helper: delay
// ---------------------------------------------------------------------------

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

// ---------------------------------------------------------------------------
// Helper: typewriter stream into state
// ---------------------------------------------------------------------------

async function typewriterStream(
  text: string,
  setSection: (s: string | null) => void,
  setStreaming: (b: boolean) => void,
  setStreamText: React.Dispatch<React.SetStateAction<string>>,
  sectionName: string,
  signal: AbortSignal,
  chunkSize = 8,
  chunkDelay = 40,
) {
  setSection(sectionName)
  setStreaming(true)
  setStreamText('')
  for (let i = 0; i < text.length; i += chunkSize) {
    if (signal.aborted) return
    await delay(chunkDelay)
    const chunk = text.slice(i, i + chunkSize)
    setStreamText((prev) => prev + chunk)
  }
  await delay(300)
  setStreaming(false)
  setSection(null)
  setStreamText('')
}

// ---------------------------------------------------------------------------
// Sidebar icons (copied from ChatSidebar to avoid hook dependencies)
// ---------------------------------------------------------------------------

function CollapseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 3l5 5-5 5" />
    </svg>
  )
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// DemoChatSidebarInner — reads from ChatContext
// ---------------------------------------------------------------------------

function DemoChatSidebarInner({
  transitionReady,
  suggestionChips,
  onChipClick,
}: {
  transitionReady: boolean
  suggestionChips: string[]
  onChipClick?: (chip: string) => void
}) {
  // We import useChatContext logic inline to avoid the throw when outside real provider
  const ctx = useContextDirect()
  if (!ctx) return null

  return (
    <div
      className={`flex-shrink-0 border-l border-border bg-surface transition-all duration-300 ease-in-out ${
        ctx.isOpen ? 'w-[320px] xl:w-[400px]' : 'w-[40px]'
      }`}
      role="complementary"
      aria-label="AI Chat Sidebar"
    >
      {/* Collapsed state */}
      {!ctx.isOpen && (
        <div className="flex flex-col items-center h-full pt-3">
          <button
            onClick={ctx.toggleChat}
            className="relative p-2 rounded-md text-text-muted hover:text-accent-cyan hover:bg-surface-alt transition-colors bg-transparent border-none cursor-pointer"
            aria-label="Open AI Chat"
          >
            <ChatIcon />
          </button>
        </div>
      )}

      {/* Expanded state */}
      {ctx.isOpen && (
        <div className="flex flex-col h-full overflow-hidden">
          {/* Header */}
          <div className="flex items-center gap-2 px-4 py-3 border-b border-border-solid bg-surface flex-shrink-0">
            <div className="w-2 h-2 rounded-full bg-accent-cyan" />
            <h3 className="text-sm font-semibold font-title text-text">
              AI Strategist
            </h3>
            {ctx.isStreaming && (
              <span className="text-[11px] text-accent-cyan animate-pulse truncate max-w-[140px]">
                {ctx.thinkingStatus}
              </span>
            )}
            <div className="ml-auto flex items-center gap-1">
              <button
                onClick={ctx.toggleChat}
                className="p-1.5 rounded-md text-text-muted hover:text-text hover:bg-surface-alt transition-colors bg-transparent border-none cursor-pointer"
                title="Collapse chat"
                aria-label="Collapse chat sidebar"
              >
                <CollapseIcon />
              </button>
            </div>
          </div>

          {/* Messages */}
          <ChatMessages
            messages={ctx.messages}
            isStreaming={ctx.isStreaming}
            streamingText={ctx.streamingText}
            isLoading={false}
            toolCalls={ctx.toolCalls}
            isThinking={ctx.isThinking}
            thinkingStatus={ctx.thinkingStatus}
          />

          {/* Phase transition banner */}
          {transitionReady && (
            <div className="mx-3 my-1.5 flex-shrink-0">
              <div className="bg-accent-cyan/10 border border-accent-cyan/30 rounded-lg px-3 py-2">
                <div className="flex items-start gap-2">
                  <span className="text-accent-cyan flex-shrink-0 mt-0.5">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="8" cy="8" r="6.5" />
                      <path d="M5.5 8l2 2 3.5-3.5" />
                    </svg>
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-text leading-snug">
                      Strategy phase complete!
                    </p>
                    <p className="text-[11px] text-text-muted mt-0.5">
                      Ready to move to: Contacts
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Suggestion chips */}
          {suggestionChips.length > 0 && (
            <div className="px-3 py-2 border-t border-border flex-shrink-0">
              <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-hide">
                <span className="text-[10px] text-text-dim whitespace-nowrap flex-shrink-0">Next:</span>
                {suggestionChips.map((chip) => (
                  <button
                    key={chip}
                    onClick={() => onChipClick?.(chip)}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium rounded-full border border-border-solid bg-surface-alt text-text-muted hover:text-text hover:border-accent/40 hover:bg-accent/5 transition-colors whitespace-nowrap cursor-pointer flex-shrink-0"
                  >
                    {chip}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input */}
          <ChatInput
            onSend={() => {}}
            isStreaming={ctx.isStreaming}
            placeholder="Ask about your GTM strategy..."
            inputRef={ctx.chatInputRef}
          />

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

import { useContext } from 'react'

function useContextDirect() {
  return useContext(ChatContext)
}

// ---------------------------------------------------------------------------
// PlaybookDemo — main component
// ---------------------------------------------------------------------------

type DemoAct = 'onboarding' | 'research' | 'streaming' | 'transition' | 'sidebar'

export function PlaybookDemo() {
  // ---------------------------------------------------------------------------
  // Mock chat state
  // ---------------------------------------------------------------------------
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isOpen, setIsOpen] = useState(true)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [thinkingStatus, setThinkingStatus] = useState('Thinking...')
  const [toolCalls, setToolCalls] = useState<ToolCallEvent[]>([])
  const [sectionStreamingText, setSectionStreamingText] = useState('')
  const [isSectionStreaming, setIsSectionStreaming] = useState(false)
  const [streamingSection, setStreamingSection] = useState<string | null>(null)
  const chatInputRef = useRef<HTMLTextAreaElement>(null)

  // ---------------------------------------------------------------------------
  // Demo orchestration state
  // ---------------------------------------------------------------------------
  const [act, setAct] = useState<DemoAct>('onboarding')
  const [needsOnboarding, setNeedsOnboarding] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [editorContent, setEditorContent] = useState<string | null>(null)
  const [currentPhase, setCurrentPhase] = useState('strategy')
  const [unlockedPhase, setUnlockedPhase] = useState('strategy')
  const [transitionReady, setTransitionReady] = useState(false)
  const [suggestionChips, setSuggestionChips] = useState<string[]>([])
  const [isRunning, setIsRunning] = useState(false)

  // Onboarding form refs for typewriter
  const [demoDomain, setDemoDomain] = useState('')
  const [demoObjective, setDemoObjective] = useState('')

  // Abort controller for cleanup
  const abortRef = useRef<AbortController | null>(null)

  // ---------------------------------------------------------------------------
  // Mock context value
  // ---------------------------------------------------------------------------
  const contextValue = useMemo<ChatContextValue>(() => ({
    messages,
    isOpen,
    isStreaming,
    streamingText,
    isLoading: false,
    documentChanged: null,
    clearDocumentChanged: () => {},
    toolCalls,
    isThinking,
    activeToolName: null,
    thinkingStatus,
    analysisStreamingText: '',
    isAnalysisStreaming: false,
    analysisSuggestions: [],
    sectionStreamingText,
    isSectionStreaming,
    streamingSection,
    currentFinding: null,
    thinkingHistory: [],
    messageFindings: {},
    quickActions: [],
    messageQuickActions: {},
    handleQuickAction: () => {},
    toggleChat: () => setIsOpen((p) => !p),
    openChat: () => setIsOpen(true),
    closeChat: () => setIsOpen(false),
    sendMessage: () => {},
    startNewThread: () => {},
    currentPage: 'playbook',
    isOnPlaybookPage: true,
    chatInputRef,
  }), [
    messages, isOpen, isStreaming, streamingText, toolCalls,
    isThinking, thinkingStatus, sectionStreamingText,
    isSectionStreaming, streamingSection,
  ])

  // ---------------------------------------------------------------------------
  // Helper: add message
  // ---------------------------------------------------------------------------
  const addMessage = useCallback((role: 'user' | 'assistant', content: string) => {
    const msg: ChatMessage = {
      id: `demo-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      role,
      content,
      created_at: new Date().toISOString(),
      page_context: 'playbook',
    }
    setMessages((prev) => [...prev, msg])
  }, [])

  // ---------------------------------------------------------------------------
  // Helper: typewriter for form fields
  // ---------------------------------------------------------------------------
  const typeIntoField = useCallback(async (
    text: string,
    setter: React.Dispatch<React.SetStateAction<string>>,
    signal: AbortSignal,
    charDelay = 50,
  ) => {
    setter('')
    for (let i = 0; i < text.length; i++) {
      if (signal.aborted) return
      await delay(charDelay)
      setter(text.slice(0, i + 1))
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Demo loop
  // ---------------------------------------------------------------------------
  const runDemo = useCallback(async () => {
    if (isRunning) return
    setIsRunning(true)

    const controller = new AbortController()
    abortRef.current = controller
    const signal = controller.signal

    const safeDelay = async (ms: number) => {
      if (signal.aborted) throw new Error('aborted')
      await delay(ms)
      if (signal.aborted) throw new Error('aborted')
    }

    try {
      // =====================================================================
      // ACT 1: Onboarding (0:00 - 0:20)
      // =====================================================================
      setAct('onboarding')
      setNeedsOnboarding(true)
      setIsGenerating(false)
      setEditorContent(null)
      setMessages([])
      setToolCalls([])
      setIsThinking(false)
      setIsStreaming(false)
      setStreamingText('')
      setSectionStreamingText('')
      setIsSectionStreaming(false)
      setStreamingSection(null)
      setCurrentPhase('strategy')
      setUnlockedPhase('strategy')
      setTransitionReady(false)
      setSuggestionChips([])
      setDemoDomain('')
      setDemoObjective('')
      setIsOpen(true)

      await safeDelay(3000)

      // Typewriter into form fields
      await typeIntoField('acme-saas.com', setDemoDomain, signal, 60)
      await safeDelay(500)
      await typeIntoField(
        'Generate qualified B2B leads for our AI-powered analytics platform targeting mid-market companies',
        setDemoObjective,
        signal,
        30,
      )

      await safeDelay(1500)

      // "Click" Get Started
      setIsGenerating(true)
      await safeDelay(2000)

      // Transition to editor view
      setNeedsOnboarding(false)
      setIsGenerating(false)
      setEditorContent('')

      // =====================================================================
      // ACT 2: AI Research Phase (0:20 - 0:40)
      // =====================================================================
      setAct('research')

      // User message appears in chat
      addMessage('user', 'Generate a complete GTM strategy playbook for acme-saas.com targeting mid-market B2B companies.')

      await safeDelay(500)

      // Working state
      setIsThinking(true)
      setIsStreaming(true)
      setThinkingStatus('Researching your market...')
      setToolCalls([{
        tool_call_id: 'tc-1',
        tool_name: 'web_search',
        input: { query: 'acme-saas.com competitors analytics platform' },
        status: 'running',
      }])

      await safeDelay(3000)

      // Tool 1 completes
      setToolCalls([
        {
          tool_call_id: 'tc-1',
          tool_name: 'web_search',
          input: { query: 'acme-saas.com competitors analytics platform' },
          status: 'success',
          summary: 'Found 8 competitors',
          duration_ms: 2400,
        },
        {
          tool_call_id: 'tc-2',
          tool_name: 'company_research',
          input: { domain: 'acme-saas.com' },
          status: 'running',
        },
      ])
      setThinkingStatus('Analyzing company profile...')

      await safeDelay(3000)

      // Tool 2 completes
      setToolCalls([
        {
          tool_call_id: 'tc-1',
          tool_name: 'web_search',
          input: { query: 'acme-saas.com competitors analytics platform' },
          status: 'success',
          summary: 'Found 8 competitors',
          duration_ms: 2400,
        },
        {
          tool_call_id: 'tc-2',
          tool_name: 'company_research',
          input: { domain: 'acme-saas.com' },
          status: 'success',
          summary: 'Extracted key differentiators',
          duration_ms: 3100,
        },
      ])
      setThinkingStatus('Building strategy...')

      await safeDelay(2000)

      // Clear working state before streaming
      setIsThinking(false)
      setToolCalls([])

      // =====================================================================
      // ACT 3: Strategy Streaming (0:40 - 1:30)
      // =====================================================================
      setAct('streaming')

      // Stream Section 1: Executive Summary
      await typewriterStream(
        SECTION_1, setStreamingSection, setIsSectionStreaming,
        setSectionStreamingText, SECTION_1_TITLE, signal,
      )
      setEditorContent(SECTION_1)

      addMessage('assistant', 'Executive summary drafted. Moving to ICP definition.')
      await safeDelay(1500)

      // Stream Section 2: ICP
      await typewriterStream(
        SECTION_2, setStreamingSection, setIsSectionStreaming,
        setSectionStreamingText, SECTION_2_TITLE, signal,
      )
      setEditorContent(SECTION_1 + '\n\n' + SECTION_2)

      addMessage('assistant', 'ICP tiers defined. Now building outreach strategy.')
      await safeDelay(1500)

      // Stream Section 3: Outreach Strategy
      await typewriterStream(
        SECTION_3, setStreamingSection, setIsSectionStreaming,
        setSectionStreamingText, SECTION_3_TITLE, signal,
      )
      setEditorContent(SECTION_1 + '\n\n' + SECTION_2 + '\n\n' + SECTION_3)

      // Final assistant message
      setIsStreaming(false)
      addMessage('assistant', 'Strategy complete. Ready to find matching contacts?')

      await safeDelay(2000)

      // =====================================================================
      // ACT 4: Phase Transition (1:30 - 1:45)
      // =====================================================================
      setAct('transition')
      setTransitionReady(true)
      setSuggestionChips(['Find matching contacts', 'Refine ICP criteria', 'Review strategy'])

      await safeDelay(5000)

      // Auto-click "Find matching contacts"
      setSuggestionChips([])
      setTransitionReady(false)
      setUnlockedPhase('contacts')
      setCurrentPhase('contacts')

      // =====================================================================
      // ACT 5: Sidebar Interaction (1:45 - 2:00)
      // =====================================================================
      setAct('sidebar')

      // Collapse sidebar
      setIsOpen(false)
      await safeDelay(3000)

      // Expand sidebar
      setIsOpen(true)
      await safeDelay(1000)

      // Show message
      addMessage('assistant', 'I found 47 contacts matching your Tier 1 ICP. Want to review them?')

      await safeDelay(5000)

      // =====================================================================
      // Loop back
      // =====================================================================
      setIsRunning(false)
      runDemo()
    } catch {
      // Aborted — clean exit
      setIsRunning(false)
    }
  }, [isRunning, addMessage, typeIntoField])

  // ---------------------------------------------------------------------------
  // Restart handler
  // ---------------------------------------------------------------------------
  const handleRestart = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
    }
    setIsRunning(false)
    // Small delay to let abort propagate
    setTimeout(() => {
      setAct('onboarding')
      setNeedsOnboarding(true)
      setIsGenerating(false)
      setEditorContent(null)
      setMessages([])
      setToolCalls([])
      setIsThinking(false)
      setIsStreaming(false)
      setStreamingText('')
      setSectionStreamingText('')
      setIsSectionStreaming(false)
      setStreamingSection(null)
      setCurrentPhase('strategy')
      setUnlockedPhase('strategy')
      setTransitionReady(false)
      setSuggestionChips([])
      setDemoDomain('')
      setDemoObjective('')
      setIsOpen(true)
    }, 100)
  }, [])

  // Auto-start on mount
  useEffect(() => {
    if (!isRunning) {
      const timer = setTimeout(() => runDemo(), 500)
      return () => clearTimeout(timer)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortRef.current) {
        abortRef.current.abort()
      }
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <ChatContext.Provider value={contextValue}>
      <div className="flex h-full min-h-0 overflow-hidden relative">
        {/* DEMO badge */}
        <div className="absolute top-2 left-2 z-50">
          <span className="text-[10px] font-bold uppercase tracking-wider bg-accent-cyan/20 text-accent-cyan px-2 py-0.5 rounded-full border border-accent-cyan/30">
            Demo
          </span>
        </div>

        {/* Main content area */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden px-6 pt-2">
          {/* Phase indicator */}
          <PhaseIndicator
            current={currentPhase}
            unlocked={unlockedPhase}
            onNavigate={() => {}}
          />

          {/* Content area */}
          {needsOnboarding ? (
            <DemoOnboarding
              domain={demoDomain}
              objective={demoObjective}
              isGenerating={isGenerating}
            />
          ) : (
            <div className="flex-1 min-h-0 overflow-y-auto">
              <StrategyEditor
                content={editorContent}
                onUpdate={() => {}}
                editable={false}
                sectionStreamingText={sectionStreamingText}
                isSectionStreaming={isSectionStreaming}
                streamingSection={streamingSection}
              />
            </div>
          )}
        </div>

        {/* Chat sidebar */}
        <DemoChatSidebarInner
          transitionReady={transitionReady}
          suggestionChips={suggestionChips}
        />

        {/* Restart button */}
        <button
          onClick={handleRestart}
          className="absolute bottom-3 left-3 z-50 text-[11px] text-text-dim hover:text-text-muted bg-surface-alt/80 backdrop-blur-sm border border-border-solid rounded-md px-2.5 py-1 transition-colors cursor-pointer"
        >
          Restart
        </button>

        {/* Act indicator (subtle) */}
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-50">
          <span className="text-[10px] text-text-dim/50 font-mono">
            {act}
          </span>
        </div>
      </div>
    </ChatContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// DemoOnboarding — simplified onboarding form with externally-controlled values
// ---------------------------------------------------------------------------

function DemoOnboarding({
  domain,
  objective,
  isGenerating,
}: {
  domain: string
  objective: string
  isGenerating: boolean
}) {
  return (
    <div className="w-full max-w-lg mx-auto mt-12 mb-8">
      <div className="rounded-xl border border-border-solid bg-surface p-6 shadow-sm">
        {/* Welcome header */}
        <div className="mb-5">
          <h2 className="text-lg font-semibold text-text mb-1">
            Generate Your GTM Strategy
          </h2>
          <p className="text-sm text-text-muted">
            Tell us your go-to-market objective and the AI will research your
            market and draft a complete strategy playbook.
          </p>
        </div>

        {/* Company domain */}
        <div className="mb-4">
          <label className="block text-xs font-medium text-text-muted mb-1">
            Company domain
          </label>
          <div className="flex items-center gap-2">
            <svg
              width="16" height="16" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" strokeLinecap="round"
              strokeLinejoin="round" className="text-accent-cyan flex-shrink-0"
            >
              <circle cx="12" cy="12" r="10" />
              <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            </svg>
            <input
              type="text"
              value={domain}
              readOnly
              disabled={isGenerating}
              placeholder="yourcompany.com"
              className="flex-1 px-3 py-1.5 text-sm rounded-md bg-surface-alt border border-border-solid text-text placeholder:text-text-dim focus:outline-none disabled:opacity-50"
            />
          </div>
        </div>

        {/* Objective */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text mb-1">
              What is your GTM objective?
            </label>
            <textarea
              value={objective}
              readOnly
              disabled={isGenerating}
              placeholder="e.g., Generate qualified B2B leads for our SaaS product..."
              rows={3}
              className="w-full px-3 py-2 text-sm rounded-md border border-border-solid bg-surface-alt text-text placeholder:text-text-dim focus:outline-none resize-none disabled:opacity-50"
            />
          </div>

          {/* Submit */}
          <button
            type="button"
            disabled
            className="w-full py-2.5 px-4 text-sm font-medium rounded-md bg-accent text-white cursor-default disabled:opacity-40"
          >
            {isGenerating ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Generating...
              </span>
            ) : (
              'Get Started'
            )}
          </button>
        </div>

        <div className="mt-3 flex items-center justify-center">
          <span className="text-sm text-accent cursor-default">
            I&apos;ll write it myself &rarr;
          </span>
        </div>
      </div>
    </div>
  )
}
