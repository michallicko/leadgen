/**
 * ImportSuccess -- Post-import results panel with detail tabs and paginated results.
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router'
import { Tabs } from '../../components/ui/Tabs'
import { getImportResults } from '../../api/queries/useImports'
import type { ImportResponse, ImportResultItem } from '../../api/queries/useImports'

interface ImportSuccessProps {
  response: ImportResponse
  jobId: string
  onReset: () => void
}

type FilterKey = 'all' | 'created' | 'skipped' | 'updated' | 'conflicts'

function ActionBadge({ action }: { action: ImportResultItem['action'] }) {
  const styles: Record<string, string> = {
    created: 'bg-green-400/15 text-green-400',
    skipped: 'bg-amber-400/15 text-amber-400',
    updated: 'bg-blue-400/15 text-blue-400',
    error: 'bg-red-400/15 text-red-400',
  }
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[0.68rem] font-semibold uppercase ${styles[action] ?? styles.error}`}>
      {action}
    </span>
  )
}

function ResultsTable({ jobId, filter }: { jobId: string; filter: FilterKey }) {
  const [page, setPage] = useState(1)
  const [results, setResults] = useState<ImportResultItem[]>([])
  const [total, setTotal] = useState(0)
  const [perPage, setPerPage] = useState(50)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadResults = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await getImportResults(jobId, filter, page)
      setResults(data.results)
      setTotal(data.total)
      setPerPage(data.per_page)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load details')
    } finally {
      setIsLoading(false)
    }
  }, [jobId, filter, page])

  useEffect(() => {
    loadResults()
  }, [loadResults])

  // Reset page when filter changes
  useEffect(() => {
    setPage(1)
  }, [filter])

  const totalPages = Math.ceil(total / perPage)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-6 text-text-muted text-sm">
        <div className="w-4 h-4 border-2 border-border border-t-accent-cyan rounded-full animate-spin" />
        Loading details...
      </div>
    )
  }

  if (error) {
    return (
      <div className="py-4 text-sm text-red-400">{error}</div>
    )
  }

  if (results.length === 0) {
    return (
      <div className="py-6 text-sm text-text-dim text-center">No rows match this filter.</div>
    )
  }

  return (
    <div>
      <div className="max-h-[300px] overflow-auto border border-border rounded-lg mb-3">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface z-10">
            <tr className="border-b border-border">
              <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted">Row #</th>
              <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted">Contact</th>
              <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted">Company</th>
              <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted">Action</th>
              <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted">Details</th>
            </tr>
          </thead>
          <tbody>
            {results.map((row, i) => {
              // For conflict filter, render one row per conflict
              if (filter === 'conflicts' && row.conflicts && row.conflicts.length > 0) {
                return row.conflicts.map((conflict, ci) => (
                  <tr key={`${i}-${ci}`} className="border-b border-border/30">
                    <td className="py-1.5 px-3 text-text-muted">{row.row_number}</td>
                    <td className="py-1.5 px-3 text-text truncate max-w-[140px]">{row.contact_name}</td>
                    <td className="py-1.5 px-3 text-text truncate max-w-[140px]">{row.company_name}</td>
                    <td className="py-1.5 px-3 text-sm font-semibold text-text">{conflict.field}</td>
                    <td className="py-1.5 px-3">
                      <span className="text-red-400 line-through mr-2">{conflict.existing}</span>
                      <span className="text-green-400">{conflict.incoming}</span>
                    </td>
                  </tr>
                ))
              }

              return (
                <tr key={i} className="border-b border-border/30">
                  <td className="py-1.5 px-3 text-text-muted">{row.row_number}</td>
                  <td className="py-1.5 px-3 text-text truncate max-w-[140px]">{row.contact_name}</td>
                  <td className="py-1.5 px-3 text-text truncate max-w-[140px]">{row.company_name}</td>
                  <td className="py-1.5 px-3"><ActionBadge action={row.action} /></td>
                  <td className="py-1.5 px-3 text-text-muted text-xs truncate max-w-[180px]">{row.details}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          {page > 1 && (
            <button
              onClick={() => setPage((p) => p - 1)}
              className="border border-border text-text-muted px-3 py-1 rounded-md hover:bg-surface-alt transition-colors text-xs"
            >
              Previous
            </button>
          )}
          <span className="text-xs text-text-muted">
            Page {page} of {totalPages} ({total} rows)
          </span>
          {page < totalPages && (
            <button
              onClick={() => setPage((p) => p + 1)}
              className="border border-border text-text-muted px-3 py-1 rounded-md hover:bg-surface-alt transition-colors text-xs"
            >
              Next
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export function ImportSuccess({ response, jobId, onReset }: ImportSuccessProps) {
  const navigate = useNavigate()
  const { namespace } = useParams<{ namespace: string }>()
  const { created, skipped, updated, errors } = response

  const tabs = useMemo(() => [
    {
      id: 'all',
      label: 'All',
      content: <ResultsTable jobId={jobId} filter="all" />,
    },
    {
      id: 'created',
      label: 'Created',
      count: created,
      content: <ResultsTable jobId={jobId} filter="created" />,
    },
    {
      id: 'skipped',
      label: 'Skipped',
      count: skipped,
      content: <ResultsTable jobId={jobId} filter="skipped" />,
    },
    {
      id: 'updated',
      label: 'Updated',
      count: updated,
      content: <ResultsTable jobId={jobId} filter="updated" />,
    },
    {
      id: 'conflicts',
      label: 'Conflicts',
      content: <ResultsTable jobId={jobId} filter="conflicts" />,
    },
  ], [jobId, created, skipped, updated])

  return (
    <div>
      {/* Success header */}
      <div className="text-center mb-6">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-green-400/10 text-green-400 text-2xl mb-4">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </div>
        <h2 className="font-title text-lg font-semibold text-text mb-1">Import Complete</h2>
        <p className="text-sm text-text-muted">
          Successfully imported {created + updated} contacts
        </p>
      </div>

      {/* Stats row */}
      <div className="flex justify-center gap-6 mb-6">
        <div className="text-center">
          <div className="font-title text-xl font-bold text-green-400">{created}</div>
          <div className="text-[0.7rem] text-text-muted uppercase tracking-wider mt-0.5">Created</div>
        </div>
        <div className="text-center">
          <div className="font-title text-xl font-bold text-text-muted">{skipped}</div>
          <div className="text-[0.7rem] text-text-muted uppercase tracking-wider mt-0.5">Skipped</div>
        </div>
        <div className="text-center">
          <div className="font-title text-xl font-bold text-amber-400">{updated}</div>
          <div className="text-[0.7rem] text-text-muted uppercase tracking-wider mt-0.5">Updated</div>
        </div>
        <div className="text-center">
          <div className="font-title text-xl font-bold text-red-400">{errors}</div>
          <div className="text-[0.7rem] text-text-muted uppercase tracking-wider mt-0.5">Errors</div>
        </div>
      </div>

      {/* Action links */}
      <div className="flex justify-center gap-3 mb-8 flex-wrap">
        <button
          onClick={() => navigate(`/${namespace}/enrich`)}
          className="bg-accent-cyan text-bg font-semibold px-4 py-2 rounded-md hover:opacity-90 transition-opacity text-sm"
        >
          Enrich Now
        </button>
        <button
          onClick={() => navigate(`/${namespace}/contacts`)}
          className="border border-border text-text-muted px-4 py-2 rounded-md hover:bg-surface-alt transition-colors text-sm"
        >
          View Contacts
        </button>
        <button
          onClick={onReset}
          className="border border-border text-text-muted px-4 py-2 rounded-md hover:bg-surface-alt transition-colors text-sm"
        >
          Import Another
        </button>
      </div>

      {/* Detail tabs */}
      <div className="text-left">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-text-muted mb-3">
          Import Details
        </h3>
        <Tabs tabs={tabs} />
      </div>
    </div>
  )
}
