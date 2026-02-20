import { useState } from 'react'
import { RichText } from '../../components/ui/RichText'
// Local badge — not the app Badge which requires a variant like status/tier/icp

export interface ModuleField {
  label: string
  value: unknown
  type?: 'text' | 'badge' | 'score' | 'count' | 'list' | 'score_bar' | 'colored_badge' | 'tags'
  /** For colored_badge: map of value -> tailwind color classes */
  colorMap?: Record<string, string>
}

interface Props {
  title: string
  icon?: string
  fields: ModuleField[]
  enrichedAt?: string | null
  cost?: number | null
  defaultOpen?: boolean
}

const DEFAULT_COLOR_BADGE = 'bg-accent/10 text-accent-hover border-accent/20'

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
    case 'colored_badge': {
      const colorClasses = field.colorMap?.[String(value).toLowerCase()] ?? DEFAULT_COLOR_BADGE
      return (
        <span className={`px-2 py-0.5 text-xs rounded-full border ${colorClasses}`}>
          {String(value).replace(/_/g, ' ')}
        </span>
      )
    }
    case 'score_bar': {
      const num = typeof value === 'number' ? value : parseFloat(String(value))
      if (isNaN(num)) return null
      const pct = Math.min(100, Math.max(0, (num / 10) * 100))
      const barColor = num >= 7 ? 'bg-success' : num >= 4 ? 'bg-warning' : 'bg-error'
      return (
        <span className="inline-flex items-center gap-1.5">
          <span className="text-xs font-medium text-text">{num}/10</span>
          <span className="w-12 h-1.5 bg-border-solid/30 rounded-full overflow-hidden">
            <span className={`block h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
          </span>
        </span>
      )
    }
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
    case 'tags': {
      const items = Array.isArray(value) ? value : String(value).split(',').map((s) => s.trim()).filter(Boolean)
      if (items.length === 0) return null
      return (
        <span className="text-xs text-text-muted">
          {items.length} item{items.length !== 1 ? 's' : ''}
        </span>
      )
    }
    case 'list':
      if (Array.isArray(value)) {
        return (
          <span className="text-xs text-text-muted">
            {value.length} item{value.length !== 1 ? 's' : ''}
          </span>
        )
      }
      return null
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
    if (type === 'colored_badge') {
      const colorClasses = field.colorMap?.[String(value).toLowerCase()] ?? DEFAULT_COLOR_BADGE
      return (
        <span className={`px-2.5 py-1 text-xs font-medium rounded-full border ${colorClasses}`}>
          {String(value).replace(/_/g, ' ')}
        </span>
      )
    }
    if (type === 'score_bar') {
      const num = typeof value === 'number' ? value : parseFloat(String(value))
      if (isNaN(num)) return <span className="text-sm text-text">{String(value)}</span>
      const pct = Math.min(100, Math.max(0, (num / 10) * 100))
      const barColor = num >= 7 ? 'bg-success' : num >= 4 ? 'bg-warning' : 'bg-error'
      const textColor = num >= 7 ? 'text-success' : num >= 4 ? 'text-warning' : 'text-error'
      return (
        <div className="flex items-center gap-3">
          <span className={`text-lg font-bold ${textColor}`}>{num}</span>
          <span className="text-xs text-text-muted">/10</span>
          <div className="flex-1 max-w-[200px] h-2 bg-border-solid/30 rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${pct}%` }} />
          </div>
        </div>
      )
    }
    if (type === 'score') {
      return <span className="text-sm font-medium text-accent-cyan">{typeof value === 'number' ? `${value}%` : String(value)}</span>
    }
    if (type === 'count') {
      return <span className="text-sm font-medium">{String(value)}</span>
    }
    if (type === 'tags') {
      const items = Array.isArray(value) ? value.map(String) : String(value).split(',').map((s) => s.trim()).filter(Boolean)
      if (items.length === 0) return null
      return (
        <div className="flex flex-wrap gap-1.5">
          {items.map((item, i) => (
            <span key={i} className="px-2 py-0.5 text-xs bg-accent/10 text-accent-hover rounded border border-accent/20">
              {item}
            </span>
          ))}
        </div>
      )
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
    // For objects / structured data, try to render nicely
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      const obj = value as Record<string, unknown>
      return (
        <div className="space-y-1">
          {Object.entries(obj).map(([k, v]) => {
            if (v == null || v === '') return null
            return (
              <div key={k} className="flex gap-2">
                <span className="text-xs text-text-muted font-medium min-w-[100px]">{k.replace(/_/g, ' ')}:</span>
                <span className="text-sm text-text">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
              </div>
            )
          })}
        </div>
      )
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
