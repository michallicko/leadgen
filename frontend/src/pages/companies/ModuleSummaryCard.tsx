import { useState } from 'react'
import { RichText } from '../../components/ui/RichText'
// Local badge — not the app Badge which requires a variant like status/tier/icp

export interface ModuleField {
  label: string
  value: unknown
  type?: 'text' | 'badge' | 'score' | 'count' | 'list'
}

interface Props {
  title: string
  icon?: string
  fields: ModuleField[]
  enrichedAt?: string | null
  cost?: number | null
  defaultOpen?: boolean
}

/** Format a value for the summary row (collapsed view). */
function SummaryValue({ field }: { field: ModuleField }) {
  const { value, type = 'text' } = field
  if (value == null || value === '' || value === '-') return null

  switch (type) {
    case 'badge':
      return (
        <span className="px-2 py-0.5 text-xs rounded-full bg-accent/10 text-accent-hover border border-accent/20">
          {String(value)}
        </span>
      )
    case 'score':
      return (
        <span className="text-xs font-medium text-accent-cyan">
          {typeof value === 'number' ? `${value}%` : String(value)}
        </span>
      )
    case 'count':
      return (
        <span className="text-xs font-medium text-text">
          {String(value)}
        </span>
      )
    default:
      return (
        <span className="text-xs text-text-muted line-clamp-1 max-w-[200px]">
          {String(value)}
        </span>
      )
  }
}

/** Format value for expanded view (full content). */
function ExpandedField({ field }: { field: ModuleField }) {
  const { label, value, type = 'text' } = field
  if (value == null || value === '' || value === '-') return null

  const content = (() => {
    if (type === 'badge') {
      return <span className="px-2 py-0.5 text-xs rounded-full bg-accent/10 text-accent-hover border border-accent/20">{String(value)}</span>
    }
    if (type === 'score') {
      return <span className="text-sm font-medium text-accent-cyan">{typeof value === 'number' ? `${value}%` : String(value)}</span>
    }
    if (type === 'count') {
      return <span className="text-sm font-medium">{String(value)}</span>
    }
    if (type === 'list' && Array.isArray(value)) {
      const items = value.map((item, i) => {
        if (typeof item === 'string') return `${i + 1}. ${item}`
        if (typeof item === 'object' && item !== null) {
          const obj = item as Record<string, unknown>
          const title = obj.use_case || obj.title || obj.name || ''
          const desc = obj.impact || obj.description || ''
          const extra = obj.complexity ? ` (${obj.complexity})` : ''
          if (!title && !desc) return `${i + 1}. ${JSON.stringify(obj)}`
          return `${i + 1}. **${title}**${extra} — ${desc}`
        }
        return `${i + 1}. ${String(item)}`
      })
      return <RichText text={items.join('\n')} />
    }
    return <RichText text={String(value)} />
  })()

  return (
    <div>
      <h4 className="text-xs font-medium text-text-muted mb-1">{label}</h4>
      {content}
    </div>
  )
}

export function ModuleSummaryCard({ title, icon, fields, enrichedAt, cost, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen)

  // Only show fields that have values
  const populated = fields.filter((f) => f.value != null && f.value !== '' && f.value !== '-')
  if (populated.length === 0) return null

  // Summary badges: first 4 non-null fields
  const summaryFields = populated.slice(0, 4)

  return (
    <div className="border border-border/40 rounded-lg overflow-hidden">
      {/* Collapsed header / summary */}
      <button
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-surface-alt/30 transition-colors text-left"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-3 min-w-0">
          {icon && <span className="text-base flex-shrink-0">{icon}</span>}
          <h3 className="text-sm font-semibold text-text">{title}</h3>
          <div className="flex items-center gap-2 flex-wrap">
            {!open && summaryFields.map((f) => (
              <SummaryValue key={f.label} field={f} />
            ))}
          </div>
        </div>
        <svg
          className={`w-4 h-4 text-text-muted flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Expanded content */}
      {open && (
        <div className="px-4 pb-4 pt-1 border-t border-border/20 space-y-4">
          {populated.map((f) => (
            <ExpandedField key={f.label} field={f} />
          ))}
          {(enrichedAt || cost != null) && (
            <p className="text-xs text-text-dim pt-2 border-t border-border/20">
              {enrichedAt && <>Enriched {new Date(enrichedAt).toLocaleDateString()}</>}
              {cost != null && <> · ${cost.toFixed(4)}</>}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
