/**
 * ChatMermaidBlock — Renders mermaid code blocks as diagrams in chat messages.
 *
 * Uses the shared MermaidRenderer from the playbook module.
 * Provides a read-only view with toggle to see raw source.
 */

import { useState, useCallback } from 'react'
import { MermaidRenderer } from '../playbook/MermaidBlock'

interface ChatMermaidBlockProps {
  code: string
}

export function ChatMermaidBlock({ code }: ChatMermaidBlockProps) {
  const [showSource, setShowSource] = useState(false)

  const toggleSource = useCallback(() => {
    setShowSource((s) => !s)
  }, [])

  return (
    <div className="my-2 rounded-lg border border-border-solid overflow-hidden bg-surface-alt/30">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface-alt border-b border-border-solid/50">
        <div className="flex items-center gap-2">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-accent-cyan">
            <path d="M2 4h4l2 2h6v8H2V4z" />
          </svg>
          <span className="text-[10px] font-medium text-text-muted uppercase tracking-wide">
            Diagram
          </span>
        </div>
        <button
          type="button"
          onClick={toggleSource}
          className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-surface/60 text-text-muted hover:text-text hover:bg-surface border border-border-solid/50 transition-colors"
        >
          {showSource ? 'Preview' : 'Source'}
        </button>
      </div>

      {/* Diagram or source */}
      {showSource ? (
        <pre className="p-3 font-mono text-xs text-text leading-relaxed whitespace-pre-wrap overflow-x-auto">
          {code}
        </pre>
      ) : (
        <MermaidRenderer code={code} />
      )}
    </div>
  )
}
