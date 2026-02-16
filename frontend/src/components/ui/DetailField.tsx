import { useState, type ReactNode } from 'react'
import { Badge } from './Badge'
import { SourceTooltip, type SourceInfo } from './SourceTooltip'

export type { SourceInfo } from './SourceTooltip'

/* ---- FieldGrid: 2-column responsive layout ---- */

export function FieldGrid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">{children}</div>
}

/* ---- Field: read-only label + value ---- */

interface FieldProps {
  label: string
  value: string | number | boolean | null | undefined
  className?: string
  source?: SourceInfo
}

export function Field({ label, value, className = '', source }: FieldProps) {
  const display = value === null || value === undefined || value === ''
    ? '-'
    : typeof value === 'boolean'
      ? value ? 'Yes' : 'No'
      : String(value)

  return (
    <div className={className}>
      <dt className="text-xs text-text-muted mb-0.5">{label}{source && <SourceTooltip source={source} />}</dt>
      <dd className="text-sm text-text">{display}</dd>
    </div>
  )
}

/* ---- FieldLink: value rendered as a link ---- */

interface FieldLinkProps {
  label: string
  value: string | null | undefined
  href: string | null | undefined
}

export function FieldLink({ label, value, href }: FieldLinkProps) {
  return (
    <div>
      <dt className="text-xs text-text-muted mb-0.5">{label}</dt>
      <dd className="text-sm">
        {href ? (
          <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent-cyan hover:underline">
            {value || href}
          </a>
        ) : (
          <span className="text-text">{value || '-'}</span>
        )}
      </dd>
    </div>
  )
}

/* ---- FieldBadge: value rendered as a Badge ---- */

interface FieldBadgeProps {
  label: string
  value: string | null | undefined
  variant: 'status' | 'tier' | 'icp' | 'msgStatus'
}

export function FieldBadge({ label, value, variant }: FieldBadgeProps) {
  return (
    <div>
      <dt className="text-xs text-text-muted mb-0.5">{label}</dt>
      <dd className="text-sm">
        {value ? <Badge variant={variant} value={value} /> : <span className="text-text-dim">-</span>}
      </dd>
    </div>
  )
}

/* ---- EditableSelect ---- */

interface EditableSelectProps {
  label: string
  name: string
  value: string | null | undefined
  options: { value: string; label: string }[]
  onChange: (name: string, value: string) => void
}

export function EditableSelect({ label, name, value, options, onChange }: EditableSelectProps) {
  return (
    <div>
      <label className="text-xs text-text-muted mb-0.5 block">{label}</label>
      <select
        value={value || ''}
        onChange={(e) => onChange(name, e.target.value)}
        className="w-full bg-surface-alt border border-border-solid rounded-md px-2 py-1.5 text-sm text-text focus:outline-none focus:border-accent"
      >
        <option value="">-</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  )
}

/* ---- EditableTextarea ---- */

interface EditableTextareaProps {
  label: string
  name: string
  value: string | null | undefined
  onChange: (name: string, value: string) => void
  rows?: number
}

export function EditableTextarea({ label, name, value, onChange, rows = 3 }: EditableTextareaProps) {
  return (
    <div className="col-span-full">
      <label className="text-xs text-text-muted mb-0.5 block">{label}</label>
      <textarea
        value={value || ''}
        onChange={(e) => onChange(name, e.target.value)}
        rows={rows}
        className="w-full bg-surface-alt border border-border-solid rounded-md px-3 py-2 text-sm text-text resize-y focus:outline-none focus:border-accent"
      />
    </div>
  )
}

/* ---- CollapsibleSection ---- */

interface CollapsibleSectionProps {
  title: string
  defaultOpen?: boolean
  children: ReactNode
  badge?: ReactNode
}

export function CollapsibleSection({ title, defaultOpen = false, children, badge }: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  return (
    <div className="border border-border-solid rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-surface-alt hover:bg-surface-alt/80 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text">{title}</span>
          {badge}
        </div>
        <svg
          width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"
          className={`transition-transform ${isOpen ? 'rotate-180' : ''}`}
        >
          <path d="M4 6l4 4 4-4" />
        </svg>
      </button>
      {isOpen && <div className="px-4 py-4 border-t border-border-solid">{children}</div>}
    </div>
  )
}

/* ---- SectionDivider ---- */

export function SectionDivider({ title }: { title: string }) {
  return (
    <div className="mt-6 mb-3 flex items-center gap-3">
      <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">{title}</h3>
      <div className="flex-1 h-px bg-border-solid" />
    </div>
  )
}

/* ---- MiniTable ---- */

interface MiniTableColumn<T> {
  key: string
  label: string
  render?: (item: T) => ReactNode
}

interface MiniTableProps<T> {
  columns: MiniTableColumn<T>[]
  data: T[]
  onRowClick?: (item: T) => void
  emptyText?: string
}

export function MiniTable<T extends Record<string, unknown>>({ columns, data, onRowClick, emptyText = 'None' }: MiniTableProps<T>) {
  if (data.length === 0) {
    return <p className="text-sm text-text-dim italic">{emptyText}</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-solid">
            {columns.map((col) => (
              <th key={col.key} className="text-left text-xs text-text-muted font-medium py-2 px-2">{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr
              key={i}
              onClick={() => onRowClick?.(row)}
              className={`border-b border-border/50 ${onRowClick ? 'cursor-pointer hover:bg-surface-alt/50' : ''}`}
            >
              {columns.map((col) => (
                <td key={col.key} className="py-1.5 px-2 text-text">
                  {col.render ? col.render(row) : (row[col.key] as ReactNode) ?? '-'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
