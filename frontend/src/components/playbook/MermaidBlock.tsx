/**
 * MermaidBlock — Tiptap NodeView component for rendering mermaid diagrams.
 *
 * Renders mermaid code blocks as SVG diagrams with a toggle to switch
 * between diagram preview and editable source code.
 *
 * Used by the custom MermaidExtension registered in StrategyEditor.
 *
 * Security note: mermaid.render() produces sanitized SVG output (it uses
 * DOMPurify internally since v10). The SVG is safe to render via innerHTML.
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { NodeViewWrapper, NodeViewContent } from '@tiptap/react'
import type { NodeViewProps } from '@tiptap/react'

// ---------------------------------------------------------------------------
// Lazy mermaid loader (dynamic import for bundle performance)
// ---------------------------------------------------------------------------

let mermaidPromise: Promise<typeof import('mermaid')['default']> | null = null

function getMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import('mermaid').then((mod) => {
      mod.default.initialize({
        startOnLoad: false,
        theme: 'dark',
        themeVariables: {
          darkMode: true,
          background: 'transparent',
          primaryColor: '#6E2C8B',
          primaryTextColor: '#E8E0F0',
          primaryBorderColor: '#9B59B6',
          lineColor: '#8B7FA8',
          secondaryColor: '#1A3A4A',
          tertiaryColor: '#2D1F3D',
        },
      })
      return mod.default
    })
  }
  return mermaidPromise
}

// ---------------------------------------------------------------------------
// Render result type
// ---------------------------------------------------------------------------

type RenderResult =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; svg: string }
  | { status: 'error'; message: string }

// ---------------------------------------------------------------------------
// Diagram renderer (standalone, also used by ChatMermaidBlock)
// ---------------------------------------------------------------------------

interface MermaidRendererProps {
  code: string
  editable?: boolean
  onToggleSource?: () => void
}

export function MermaidRenderer({
  code,
  editable = false,
  onToggleSource,
}: MermaidRendererProps) {
  // Track the code that produced the current result to derive loading state
  const [rendered, setRendered] = useState<{ code: string; result: RenderResult }>({
    code: '',
    result: { status: 'idle' },
  })
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const trimmed = code.trim()
    if (!trimmed) return

    let cancelled = false

    async function render() {
      try {
        const m = await getMermaid()
        const renderId = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
        const { svg } = await m.render(renderId, trimmed)
        if (!cancelled) {
          setRendered({ code, result: { status: 'success', svg } })
        }
      } catch (err: unknown) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : String(err)
          const clean = msg.replace(/^.*?Parse error on line/s, 'Parse error on line')
          setRendered({ code, result: { status: 'error', message: clean || 'Invalid mermaid syntax' } })
        }
      }
    }

    render()
    return () => {
      cancelled = true
    }
  }, [code])

  // Derive display state: loading if code changed since last render completed
  const isEmpty = !code.trim()
  const isLoading = !isEmpty && rendered.code !== code
  const result = isLoading ? { status: 'loading' as const } : rendered.result

  if (isEmpty) return null

  return (
    <div className="mermaid-preview relative" ref={containerRef}>
      {/* Toggle button */}
      {editable && onToggleSource && (
        <button
          type="button"
          onClick={onToggleSource}
          className="absolute top-2 right-2 z-10 px-2 py-0.5 text-[10px] font-medium rounded bg-surface-alt/80 text-text-muted hover:text-text hover:bg-surface-alt border border-border-solid/50 transition-colors"
        >
          Edit Source
        </button>
      )}

      {/* SVG output from mermaid.render() — safe: mermaid uses DOMPurify internally */}
      {result.status === 'success' && (
        <div
          className="mermaid-svg-container flex items-center justify-center p-4 overflow-x-auto"
          dangerouslySetInnerHTML={{ __html: result.svg }}
        />
      )}

      {result.status === 'error' && (
        <div className="p-3 text-xs">
          <div className="flex items-center gap-2 text-warning mb-1">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M8 1L15 14H1L8 1z" />
              <path d="M8 6v4M8 12v.5" />
            </svg>
            <span className="font-medium">Diagram syntax error</span>
          </div>
          <pre className="text-text-dim whitespace-pre-wrap break-words font-mono text-[11px] mt-1">
            {result.message}
          </pre>
          {editable && onToggleSource && (
            <button
              type="button"
              onClick={onToggleSource}
              className="mt-2 text-accent text-[11px] hover:underline"
            >
              Edit source to fix
            </button>
          )}
        </div>
      )}

      {(result.status === 'loading' || result.status === 'idle') && (
        <div className="flex items-center justify-center p-6 text-text-dim text-xs">
          Rendering diagram...
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tiptap NodeView — dispatches between mermaid and regular code blocks
// ---------------------------------------------------------------------------

/**
 * CodeBlockNodeView — handles ALL code blocks in the editor.
 * Mermaid blocks get the rich diagram view; others get a simple pre/code.
 */
export function CodeBlockNodeView(props: NodeViewProps) {
  const isMermaid = props.node.attrs.language === 'mermaid'

  if (isMermaid) {
    return <MermaidNodeView {...props} />
  }

  // Regular code block — simple pass-through
  return (
    <NodeViewWrapper className="my-2">
      <NodeViewContent<'pre'>
        as="pre"
        className="bg-[var(--color-surface-alt)] rounded-lg p-4 font-mono text-[0.88em] leading-[1.6] overflow-x-auto"
      />
    </NodeViewWrapper>
  )
}

// ---------------------------------------------------------------------------
// Mermaid-specific NodeView
// ---------------------------------------------------------------------------

function MermaidNodeView({ node, updateAttributes, editor }: NodeViewProps) {
  const code = node.textContent || ''
  const isEditable = editor.isEditable
  // User's explicit toggle preference; when not editable, always show diagram
  const [sourceToggle, setSourceToggle] = useState(false)
  const showSource = useMemo(() => isEditable && sourceToggle, [isEditable, sourceToggle])

  const toggleSource = useCallback(() => {
    setSourceToggle((s) => !s)
  }, [])

  // Force attributes for language tracking
  useEffect(() => {
    if (node.attrs.language !== 'mermaid') {
      updateAttributes({ language: 'mermaid' })
    }
  }, [node.attrs.language, updateAttributes])

  return (
    <NodeViewWrapper className="mermaid-block my-4 rounded-lg border border-border-solid overflow-hidden bg-surface-alt/30">
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface-alt border-b border-border-solid/50">
        <div className="flex items-center gap-2">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-accent-cyan">
            <path d="M2 4h4l2 2h6v8H2V4z" />
          </svg>
          <span className="text-[11px] font-medium text-text-muted uppercase tracking-wide">
            Mermaid Diagram
          </span>
        </div>
        {isEditable && (
          <button
            type="button"
            onClick={toggleSource}
            className="px-2 py-0.5 text-[10px] font-medium rounded bg-surface/60 text-text-muted hover:text-text hover:bg-surface border border-border-solid/50 transition-colors"
          >
            {showSource ? 'Preview' : 'Source'}
          </button>
        )}
      </div>

      {/* Diagram preview (when not showing source) */}
      {!showSource && (
        <MermaidRenderer
          code={code}
          editable={isEditable}
          onToggleSource={toggleSource}
        />
      )}

      {/* Editable source code (NodeViewContent renders ProseMirror content) */}
      <div className={showSource ? 'block' : 'hidden'}>
        <NodeViewContent<'pre'>
          as="pre"
          className="mermaid-source p-4 font-mono text-sm text-text leading-relaxed outline-none whitespace-pre-wrap"
        />
      </div>
    </NodeViewWrapper>
  )
}
