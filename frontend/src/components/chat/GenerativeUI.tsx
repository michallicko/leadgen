/**
 * GenerativeUI — renders rich inline components in chat based on
 * AG-UI STATE_DELTA events with component payloads.
 *
 * Supports: DataTable, ProgressCard, ComparisonView.
 * Falls back to formatted JSON text when component type is unknown.
 */

import { useState, useMemo } from 'react'
import type {
  GenerativeUIComponentType,
  DataTableProps,
  ProgressCardProps,
  ComparisonViewProps,
} from '../../types/agui'

// ---------------------------------------------------------------------------
// DataTable component
// ---------------------------------------------------------------------------

function DataTable({ title, columns, rows }: DataTableProps) {
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortAsc, setSortAsc] = useState(true)

  const sortedRows = useMemo(() => {
    if (!sortKey) return rows
    return [...rows].sort((a, b) => {
      const aVal = String(a[sortKey] ?? '')
      const bVal = String(b[sortKey] ?? '')
      return sortAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
    })
  }, [rows, sortKey, sortAsc])

  const handleSort = (key: string, sortable?: boolean) => {
    if (!sortable) return
    if (sortKey === key) {
      setSortAsc(!sortAsc)
    } else {
      setSortKey(key)
      setSortAsc(true)
    }
  }

  return (
    <div className="rounded-lg border border-border-solid overflow-hidden my-2">
      {title && (
        <div className="px-3 py-2 bg-surface-alt border-b border-border-solid">
          <span className="text-xs font-medium text-text-muted uppercase tracking-wide">{title}</span>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-alt/50">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-3 py-2 text-left text-xs font-medium text-text-muted uppercase tracking-wide
                    ${col.sortable ? 'cursor-pointer hover:text-text select-none' : ''}`}
                  onClick={() => handleSort(col.key, col.sortable)}
                >
                  {col.label}
                  {sortKey === col.key && (
                    <span className="ml-1">{sortAsc ? '\u2191' : '\u2193'}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {sortedRows.map((row, i) => (
              <tr key={i} className="hover:bg-surface-alt/30 transition-colors">
                {columns.map((col) => (
                  <td key={col.key} className="px-3 py-2 text-text">
                    {String(row[col.key] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ProgressCard component
// ---------------------------------------------------------------------------

function ProgressCard({ title, progress, status, details }: ProgressCardProps) {
  const clampedProgress = Math.max(0, Math.min(100, progress))

  return (
    <div className="rounded-lg border border-border-solid bg-surface p-3 my-2 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-text">{title}</span>
        <span className="text-xs text-text-muted">{clampedProgress}%</span>
      </div>
      <div className="w-full h-2 bg-surface-alt rounded-full overflow-hidden">
        <div
          className="h-full bg-accent rounded-full transition-all duration-500 ease-out"
          style={{ width: `${clampedProgress}%` }}
        />
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xs text-text-muted">{status}</span>
        {details && <span className="text-xs text-text-muted">{details}</span>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ComparisonView component
// ---------------------------------------------------------------------------

function ComparisonView({ title, items }: ComparisonViewProps) {
  return (
    <div className="my-2 space-y-2">
      {title && (
        <span className="text-xs font-medium text-text-muted uppercase tracking-wide">{title}</span>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {items.map((item, i) => (
          <div
            key={i}
            className="rounded-lg border border-border-solid bg-surface p-3 space-y-2"
          >
            <h4 className="text-sm font-medium text-text">{item.label}</h4>
            <p className="text-xs text-text-muted leading-relaxed">{item.description}</p>
            {item.pros && item.pros.length > 0 && (
              <div>
                <span className="text-xs font-medium text-green-600 dark:text-green-400">Pros:</span>
                <ul className="text-xs text-text-muted ml-3 list-disc">
                  {item.pros.map((pro, j) => <li key={j}>{pro}</li>)}
                </ul>
              </div>
            )}
            {item.cons && item.cons.length > 0 && (
              <div>
                <span className="text-xs font-medium text-red-600 dark:text-red-400">Cons:</span>
                <ul className="text-xs text-text-muted ml-3 list-disc">
                  {item.cons.map((con, j) => <li key={j}>{con}</li>)}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Text fallback for unknown component types
// ---------------------------------------------------------------------------

function TextFallback({ props }: { props: Record<string, unknown> }) {
  return (
    <div className="rounded-lg border border-border-solid bg-surface-alt p-3 my-2">
      <pre className="text-xs text-text-muted whitespace-pre-wrap font-mono overflow-x-auto">
        {JSON.stringify(props, null, 2)}
      </pre>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main renderer
// ---------------------------------------------------------------------------

interface GenerativeUIRendererProps {
  componentType: GenerativeUIComponentType | string
  props: Record<string, unknown>
}

export function GenerativeUIRenderer({ componentType, props }: GenerativeUIRendererProps) {
  switch (componentType) {
    case 'data_table':
      return <DataTable {...(props as unknown as DataTableProps)} />
    case 'progress_card':
      return <ProgressCard {...(props as unknown as ProgressCardProps)} />
    case 'comparison_view':
      return <ComparisonView {...(props as unknown as ComparisonViewProps)} />
    default:
      return <TextFallback props={props} />
  }
}
