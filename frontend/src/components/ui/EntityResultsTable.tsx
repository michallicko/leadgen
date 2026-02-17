/**
 * EntityResultsTable — reusable table for entity processing results.
 * Used by: run history modal, corrective action modal, failed entities view.
 */

import { type ReactNode } from 'react'

export interface EntityResult {
  entity_id: string
  entity_name: string
  entity_type: 'company' | 'contact'
  stage: string
  status: string
  error?: string
  cost_usd?: number
  completed_at?: string
}

interface EntityResultsTableProps {
  results: EntityResult[]
  isLoading?: boolean
  actions?: (item: EntityResult) => ReactNode
  onEntityClick?: (type: string, id: string) => void
  emptyText?: string
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-success/15 text-success border-success/30',
  failed: 'bg-error/15 text-error border-error/30',
  needs_review: 'bg-warning/15 text-warning border-warning/30',
  running: 'bg-[#00B8CF]/15 text-[#00B8CF] border-[#00B8CF]/30',
  pending: 'bg-[#8B92A0]/10 text-text-muted border-[#8B92A0]/20',
  skipped: 'bg-[#8B92A0]/10 text-text-dim border-[#8B92A0]/20',
}

function fmtCost(v: number | undefined): string {
  if (v === undefined || v === null) return '-'
  if (v === 0) return 'free'
  if (v < 0.01) return `$${v.toFixed(4)}`
  return `$${v.toFixed(2)}`
}

function fmtDate(iso: string | undefined): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function EntityResultsTable({
  results,
  isLoading,
  actions,
  onEntityClick,
  emptyText = 'No results.',
}: EntityResultsTableProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-6 h-6 border-2 border-border border-t-accent rounded-full animate-spin" />
        <span className="ml-2 text-sm text-text-muted">Loading...</span>
      </div>
    )
  }

  if (results.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-text-dim">
        <p className="text-sm">{emptyText}</p>
      </div>
    )
  }

  return (
    <div className="overflow-auto border border-border-solid rounded-lg bg-surface">
      <table className="w-full text-sm border-collapse" style={{ minWidth: 600 }}>
        <thead className="sticky top-0 z-10 bg-surface-alt">
          <tr>
            <th className="text-left text-xs font-medium text-text-muted px-3 py-2.5 border-b border-border-solid">Name</th>
            <th className="text-left text-xs font-medium text-text-muted px-3 py-2.5 border-b border-border-solid">Type</th>
            <th className="text-left text-xs font-medium text-text-muted px-3 py-2.5 border-b border-border-solid">Stage</th>
            <th className="text-left text-xs font-medium text-text-muted px-3 py-2.5 border-b border-border-solid">Status</th>
            <th className="text-left text-xs font-medium text-text-muted px-3 py-2.5 border-b border-border-solid">Error</th>
            <th className="text-left text-xs font-medium text-text-muted px-3 py-2.5 border-b border-border-solid">Cost</th>
            <th className="text-left text-xs font-medium text-text-muted px-3 py-2.5 border-b border-border-solid">Time</th>
            {actions && (
              <th className="text-left text-xs font-medium text-text-muted px-3 py-2.5 border-b border-border-solid">Actions</th>
            )}
          </tr>
        </thead>
        <tbody>
          {results.map((item) => {
            const statusStyle = STATUS_COLORS[item.status] ?? STATUS_COLORS.pending
            return (
              <tr key={`${item.entity_id}-${item.stage}`} className="border-b border-border/30">
                <td className="px-3 py-2 text-text">
                  {onEntityClick ? (
                    <button
                      onClick={() => onEntityClick(item.entity_type, item.entity_id)}
                      className="text-accent-cyan hover:underline text-left"
                    >
                      {item.entity_name}
                    </button>
                  ) : (
                    item.entity_name
                  )}
                </td>
                <td className="px-3 py-2 text-text-muted capitalize">{item.entity_type}</td>
                <td className="px-3 py-2 text-text-muted">{item.stage}</td>
                <td className="px-3 py-2">
                  <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border whitespace-nowrap ${statusStyle}`}>
                    {item.status}
                  </span>
                </td>
                <td className="px-3 py-2 text-text-muted max-w-[200px] truncate" title={item.error}>
                  {item.error ?? '-'}
                </td>
                <td className="px-3 py-2 text-text-muted">{fmtCost(item.cost_usd)}</td>
                <td className="px-3 py-2 text-text-muted whitespace-nowrap">{fmtDate(item.completed_at)}</td>
                {actions && (
                  <td className="px-3 py-2">{actions(item)}</td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
