/**
 * PlaybookDemo -- dev-only page that simulates the chat + editor integration
 * without any LLM calls. Useful for testing typewriter streaming, sidebar
 * toggle, and editor content updates in isolation.
 *
 * Route: /:namespace/playbook-demo
 */

import { useState, useCallback } from 'react'
import { StrategyEditor } from '../../components/playbook/StrategyEditor'

// ---------------------------------------------------------------------------
// Mock content
// ---------------------------------------------------------------------------

const INITIAL_CONTENT = `# GTM Strategy Playbook

## Executive Summary

This is a sample strategy document for testing the editor and streaming effects.

## Target Market

Mid-market B2B SaaS companies with 50-500 employees in North America and Europe.

### Key Segments

- **Enterprise SaaS**: Companies with ARR > $10M seeking growth acceleration
- **Growth-stage startups**: Series B/C companies building outbound motions
- **Professional services**: Consulting firms expanding into new verticals
`

const MOCK_STREAMING_CONTENT = `## Market Positioning

Our platform targets mid-market B2B SaaS companies with a focus on founder-led sales teams transitioning to scalable outbound motions.

### Key Differentiators

- **AI-powered lead scoring** that learns from your closed-won patterns
- **Automated outreach sequences** with multi-channel orchestration
- **Real-time intent signals** from hiring patterns, tech stack changes, and funding events

### Competitive Landscape

Unlike traditional sales engagement platforms (Outreach, Salesloft), we integrate the entire research-to-outreach pipeline into a single workflow. The AI doesn't just send emails — it identifies the right companies, finds the right contacts, and crafts personalized messages based on deep company research.

### Positioning Statement

For B2B founders who need predictable pipeline without hiring a sales team, our platform provides an AI-powered GTM engine that automates the entire outbound workflow from company identification to personalized outreach.`

// ---------------------------------------------------------------------------
// PlaybookDemo
// ---------------------------------------------------------------------------

export function PlaybookDemo() {
  const [content, setContent] = useState<string | null>(INITIAL_CONTENT)
  const [isSectionStreaming, setIsSectionStreaming] = useState(false)
  const [sectionStreamingText, setSectionStreamingText] = useState('')
  const [streamingSection, setStreamingSection] = useState<string | null>(null)
  const [status, setStatus] = useState('Ready')
  const [isSimulating, setIsSimulating] = useState(false)

  // Editor update handler (no-op save for demo)
  const handleEditorUpdate = useCallback((newContent: string) => {
    setContent(newContent)
  }, [])

  // ---------------------------------------------------------------------------
  // Simulation: Section streaming with typewriter
  // ---------------------------------------------------------------------------

  const simulateStreamingUpdate = useCallback(async () => {
    if (isSimulating) return
    setIsSimulating(true)
    setStatus('Starting section stream...')

    // Simulate section_content_start
    setIsSectionStreaming(true)
    setStreamingSection('Market Positioning')
    setSectionStreamingText('')

    // Simulate chunks arriving (10 chars at a time, 50ms apart)
    const chunkSize = 10
    for (let i = 0; i < MOCK_STREAMING_CONTENT.length; i += chunkSize) {
      await new Promise(r => setTimeout(r, 50))
      const chunk = MOCK_STREAMING_CONTENT.slice(0, i + chunkSize)
      setSectionStreamingText(chunk)
      if (i % 100 === 0) {
        setStatus(`Streaming... ${Math.min(100, Math.round((i / MOCK_STREAMING_CONTENT.length) * 100))}%`)
      }
    }

    setStatus('Stream complete, fading out...')

    // Simulate section_content_done
    await new Promise(r => setTimeout(r, 500))
    setIsSectionStreaming(false)
    setSectionStreamingText('')
    setStreamingSection(null)

    // Simulate editor content update (as if refetch happened)
    await new Promise(r => setTimeout(r, 300))
    setContent(INITIAL_CONTENT + '\n' + MOCK_STREAMING_CONTENT)
    setStatus('Done -- content merged into editor')
    setIsSimulating(false)
  }, [isSimulating])

  // ---------------------------------------------------------------------------
  // Simulation: Quick burst (short text, fast)
  // ---------------------------------------------------------------------------

  const simulateQuickBurst = useCallback(async () => {
    if (isSimulating) return
    setIsSimulating(true)
    setStatus('Quick burst...')

    const shortText = '### Action Items\n\n1. Define ICP criteria\n2. Build target account list\n3. Set up outreach sequences'

    setIsSectionStreaming(true)
    setStreamingSection('Action Items')
    setSectionStreamingText('')

    const chunkSize = 8
    for (let i = 0; i < shortText.length; i += chunkSize) {
      await new Promise(r => setTimeout(r, 30))
      setSectionStreamingText(shortText.slice(0, i + chunkSize))
    }

    await new Promise(r => setTimeout(r, 400))
    setIsSectionStreaming(false)
    setSectionStreamingText('')
    setStreamingSection(null)

    setStatus('Quick burst complete')
    setIsSimulating(false)
  }, [isSimulating])

  // ---------------------------------------------------------------------------
  // Simulation: Reset editor content
  // ---------------------------------------------------------------------------

  const resetContent = useCallback(() => {
    setContent(INITIAL_CONTENT)
    setStatus('Content reset to initial state')
  }, [])

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 mb-3 flex-shrink-0">
        <h1 className="font-title text-[1.3rem] font-semibold tracking-tight">
          Playbook Demo
        </h1>
        <span className="text-xs text-text-dim bg-surface-alt px-2 py-0.5 rounded-full">
          Dev Only
        </span>
      </div>

      {/* Control panel */}
      <div className="flex flex-wrap items-center gap-2 mb-3 p-3 rounded-lg border border-border-solid bg-surface-alt flex-shrink-0">
        <span className="text-xs font-medium text-text-muted mr-2">Simulate:</span>

        <button
          onClick={simulateStreamingUpdate}
          disabled={isSimulating}
          className="px-3 py-1.5 text-xs font-medium rounded-md bg-accent text-white hover:bg-accent-hover transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed border-0"
        >
          Section Stream (long)
        </button>

        <button
          onClick={simulateQuickBurst}
          disabled={isSimulating}
          className="px-3 py-1.5 text-xs font-medium rounded-md bg-accent/80 text-white hover:bg-accent transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed border-0"
        >
          Quick Burst (short)
        </button>

        <button
          onClick={resetContent}
          disabled={isSimulating}
          className="px-3 py-1.5 text-xs font-medium rounded-md border border-border-solid text-text-muted hover:bg-surface hover:text-text transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed bg-transparent"
        >
          Reset Content
        </button>

        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-text-dim">Status:</span>
          <span className="text-xs font-mono text-accent">{status}</span>
        </div>
      </div>

      {/* Editor */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <StrategyEditor
          content={content}
          onUpdate={handleEditorUpdate}
          editable={true}
          sectionStreamingText={sectionStreamingText}
          isSectionStreaming={isSectionStreaming}
          streamingSection={streamingSection}
        />
      </div>
    </div>
  )
}
