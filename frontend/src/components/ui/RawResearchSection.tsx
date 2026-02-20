import { useState } from 'react'

interface Props {
  title?: string
  data: Record<string, unknown> | null | undefined
  subtitle?: string
}

/**
 * Renders raw research / LLM response data in a collapsible, readable format.
 * Shows JSON key-value pairs in a monospace style with progressive disclosure.
 */
export function RawResearchSection({ title = 'Raw Intelligence', data, subtitle }: Props) {
  const [open, setOpen] = useState(false)

  if (!data || Object.keys(data).length === 0) return null

  return (
    <section className="border border-border/40 rounded-lg overflow-hidden mt-4">
      <button
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-500/5 transition-colors text-left bg-gray-500/5"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          <span className="text-base flex-shrink-0">&#128220;</span>
          <h3 className="text-sm font-semibold text-text-muted">{title}</h3>
          <span className="text-xs text-text-dim">({Object.keys(data).length} fields)</span>
        </div>
        <svg
          className={`w-4 h-4 text-text-muted flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="px-4 pb-4 pt-3 border-t border-border/20 bg-gray-500/5">
          {subtitle && (
            <p className="text-xs text-text-dim italic mb-3">{subtitle}</p>
          )}
          <div className="space-y-2">
            {Object.entries(data).map(([key, value]) => {
              if (value == null || value === '') return null
              return <RawField key={key} fieldKey={key} value={value} />
            })}
          </div>
        </div>
      )}
    </section>
  )
}

function RawField({ fieldKey, value }: { fieldKey: string; value: unknown }) {
  const [expanded, setExpanded] = useState(false)
  const label = fieldKey.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

  // Simple scalar values
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    const strVal = String(value)
    const isLong = strVal.length > 200

    return (
      <div className="border-b border-border/10 pb-2 last:border-b-0">
        <span className="text-xs font-medium text-text-muted">{label}</span>
        <div className={`text-sm text-text mt-0.5 font-mono leading-relaxed ${isLong && !expanded ? 'line-clamp-3' : ''}`}>
          {strVal}
        </div>
        {isLong && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-accent-cyan hover:underline mt-0.5"
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </div>
    )
  }

  // Arrays
  if (Array.isArray(value)) {
    if (value.length === 0) return null
    return (
      <div className="border-b border-border/10 pb-2 last:border-b-0">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs font-medium text-text-muted hover:text-text transition-colors"
        >
          <svg
            className={`w-3 h-3 transition-transform ${expanded ? 'rotate-90' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          {label} ({value.length} items)
        </button>
        {expanded && (
          <div className="mt-1 ml-4 space-y-1">
            {value.map((item, i) => (
              <div key={i} className="text-sm text-text font-mono bg-surface-alt/30 rounded px-2 py-1">
                {typeof item === 'object' ? JSON.stringify(item, null, 2) : String(item)}
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  // Objects
  if (typeof value === 'object' && value !== null) {
    const entries = Object.entries(value as Record<string, unknown>).filter(([, v]) => v != null && v !== '')
    if (entries.length === 0) return null

    return (
      <div className="border-b border-border/10 pb-2 last:border-b-0">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs font-medium text-text-muted hover:text-text transition-colors"
        >
          <svg
            className={`w-3 h-3 transition-transform ${expanded ? 'rotate-90' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          {label} ({entries.length} fields)
        </button>
        {expanded && (
          <div className="mt-1 ml-4 space-y-1">
            {entries.map(([k, v]) => (
              <div key={k} className="text-sm font-mono">
                <span className="text-text-muted">{k.replace(/_/g, ' ')}:</span>{' '}
                <span className="text-text">
                  {typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  return null
}
