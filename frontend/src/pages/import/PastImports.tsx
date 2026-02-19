/**
 * PastImports -- Recent imports list shown below the wizard.
 */

import { useState, useCallback } from 'react'
import { useImports, getImportStatus } from '../../api/queries/useImports'
import type { ColumnMapping, PreviewResponse } from '../../api/queries/useImports'

interface PastImportsProps {
  onResume: (jobId: string, mapping: ColumnMapping[], preview: PreviewResponse | null) => void
}

const STATUS_STYLES: Record<string, string> = {
  uploaded: 'bg-blue-400/15 text-blue-400',
  mapped: 'bg-amber-400/15 text-amber-400',
  previewed: 'bg-amber-400/15 text-amber-400',
  completed: 'bg-green-400/15 text-green-400',
  failed: 'bg-red-400/15 text-red-400',
}

function formatDate(dateStr: string) {
  try {
    return new Date(dateStr).toLocaleDateString()
  } catch {
    return dateStr
  }
}

export function PastImports({ onResume }: PastImportsProps) {
  const { data, isLoading } = useImports()
  const [resumingId, setResumingId] = useState<string | null>(null)

  const handleResume = useCallback(async (jobId: string) => {
    setResumingId(jobId)
    try {
      const status = await getImportStatus(jobId)
      onResume(jobId, status.mapping ?? [], status.preview ?? null)
    } catch {
      // Resume failed silently
    } finally {
      setResumingId(null)
    }
  }, [onResume])

  const imports = data?.imports ?? []
  const canResume = (status: string) =>
    status === 'uploaded' || status === 'mapped' || status === 'previewed'

  return (
    <div className="bg-surface border border-border rounded-lg p-6">
      <h3 className="font-title text-sm font-semibold uppercase tracking-wider text-text-muted mb-4">
        Recent Imports
      </h3>

      {isLoading && (
        <div className="flex items-center gap-2 text-text-dim text-sm py-2">
          <div className="w-3 h-3 border-2 border-border border-t-accent-cyan rounded-full animate-spin" />
          Loading...
        </div>
      )}

      {!isLoading && imports.length === 0 && (
        <div className="text-text-dim text-sm py-2">No previous imports</div>
      )}

      {!isLoading && imports.length > 0 && (
        <div className="space-y-0">
          {imports.map((job) => (
            <div
              key={job.id}
              className="flex items-center gap-4 py-3 border-b border-border/30 last:border-b-0 text-sm"
            >
              {/* Filename */}
              <span className="font-medium text-text flex-1 min-w-0 truncate">
                {job.filename}
              </span>

              {/* Row count */}
              <span className="text-text-dim text-xs whitespace-nowrap">
                {job.row_count} rows
              </span>

              {/* Date */}
              <span className="text-text-dim text-xs whitespace-nowrap">
                {formatDate(job.created_at)}
              </span>

              {/* Status pill */}
              <span className={`inline-block px-2.5 py-0.5 rounded text-[0.72rem] font-semibold uppercase ${STATUS_STYLES[job.status] ?? STATUS_STYLES.failed}`}>
                {job.status}
              </span>

              {/* Stats (if completed) */}
              {job.status === 'completed' && job.stats && (
                <span className="text-text-dim text-xs whitespace-nowrap">
                  {job.stats.created} created, {job.stats.skipped} skipped
                </span>
              )}

              {/* Resume button */}
              {canResume(job.status) && (
                <button
                  onClick={() => handleResume(job.id)}
                  disabled={resumingId === job.id}
                  className="px-2.5 py-1 rounded border border-accent-cyan text-accent-cyan text-[0.72rem] font-semibold hover:bg-accent-cyan hover:text-bg transition-colors disabled:opacity-50"
                >
                  {resumingId === job.id ? 'Loading...' : 'Resume'}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
