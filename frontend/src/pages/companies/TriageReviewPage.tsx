import { useState, useCallback } from 'react'
import { useTriageQueue, useTriageCompany, type TriageQueueItem, type TriageAction } from '../../api/queries/useCompanies'
import { useToast } from '../../components/ui/Toast'
import { Badge } from '../../components/ui/Badge'

// ── Score bar helper ──────────────────────────────────────

function ScoreBar({ value, max = 10 }: { value: number | null; max?: number }) {
  if (value == null) return <span className="text-text-dim text-xs">-</span>
  const pct = Math.min(100, (value / max) * 100)
  const color = pct >= 70 ? 'bg-success' : pct >= 40 ? 'bg-warning' : 'bg-error'
  return (
    <span className="inline-flex items-center gap-1.5 text-xs tabular-nums">
      <span className="w-10 h-1.5 rounded-full bg-surface-alt overflow-hidden">
        <span className={`block h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </span>
      {value.toFixed(1)}
    </span>
  )
}

// ── Triage card ───────────────────────────────────────────

interface TriageCardProps {
  company: TriageQueueItem
  onAction: (id: string, action: TriageAction, reason?: string) => void
  isLoading: boolean
}

function TriageCard({ company, onAction, isLoading }: TriageCardProps) {
  const [showReason, setShowReason] = useState(false)
  const [reason, setReason] = useState('')

  const handleDisqualify = () => {
    if (!showReason) {
      setShowReason(true)
      return
    }
    if (!reason.trim()) return
    onAction(company.id, 'disqualify', reason.trim())
    setShowReason(false)
    setReason('')
  }

  const handlePass = () => {
    onAction(company.id, 'pass')
    setShowReason(false)
    setReason('')
  }

  const handleReview = () => {
    onAction(company.id, 'review', reason.trim() || undefined)
    setShowReason(false)
    setReason('')
  }

  return (
    <div className="bg-surface rounded-lg border border-border p-4 space-y-3">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-text truncate">{company.name}</h3>
          {company.domain && (
            <p className="text-xs text-text-muted truncate mt-0.5">{company.domain}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {company.tier && <Badge variant="tier" value={company.tier} />}
          {company.status && <Badge variant="status" value={company.status} />}
        </div>
      </div>

      {/* Key data row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1.5">
        <div>
          <span className="text-[10px] text-text-dim uppercase tracking-wider">Score</span>
          <div><ScoreBar value={company.triage_score} /></div>
        </div>
        <div>
          <span className="text-[10px] text-text-dim uppercase tracking-wider">Pre-Score</span>
          <div><ScoreBar value={company.pre_score} /></div>
        </div>
        <div>
          <span className="text-[10px] text-text-dim uppercase tracking-wider">Industry</span>
          <p className="text-xs text-text truncate">{company.industry || '-'}</p>
        </div>
        <div>
          <span className="text-[10px] text-text-dim uppercase tracking-wider">Country</span>
          <p className="text-xs text-text truncate">{company.hq_country || '-'}</p>
        </div>
        <div>
          <span className="text-[10px] text-text-dim uppercase tracking-wider">Size</span>
          <p className="text-xs text-text truncate">{company.company_size || '-'}</p>
        </div>
        <div>
          <span className="text-[10px] text-text-dim uppercase tracking-wider">Revenue</span>
          <p className="text-xs text-text truncate">{company.revenue_range || '-'}</p>
        </div>
        <div>
          <span className="text-[10px] text-text-dim uppercase tracking-wider">Confidence</span>
          <div><ScoreBar value={company.confidence} max={1} /></div>
        </div>
        <div>
          <span className="text-[10px] text-text-dim uppercase tracking-wider">Owner</span>
          <p className="text-xs text-text truncate">{company.owner_name || '-'}</p>
        </div>
      </div>

      {/* Triage notes from L1 */}
      {company.triage_notes && (
        <div className="bg-surface-alt rounded-md border border-border px-3 py-2">
          <p className="text-[10px] text-text-dim uppercase tracking-wider mb-0.5">L1 Triage Notes</p>
          <p className="text-xs text-text-muted line-clamp-3">{company.triage_notes}</p>
        </div>
      )}

      {/* Reason input for disqualify/review */}
      {showReason && (
        <div>
          <textarea
            className="w-full bg-surface-alt border border-border rounded-md px-3 py-2 text-xs text-text placeholder:text-text-dim focus:outline-none focus:ring-1 focus:ring-accent resize-none"
            rows={2}
            placeholder="Reason for disqualification (required)..."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            autoFocus
          />
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-2 pt-1">
        <button
          type="button"
          onClick={handlePass}
          disabled={isLoading}
          className="flex-1 px-3 py-1.5 text-xs font-medium rounded-md bg-success/15 text-success border border-success/30 hover:bg-success/25 transition-colors disabled:opacity-50"
        >
          Pass
        </button>
        <button
          type="button"
          onClick={handleReview}
          disabled={isLoading}
          className="flex-1 px-3 py-1.5 text-xs font-medium rounded-md bg-warning/15 text-warning border border-warning/30 hover:bg-warning/25 transition-colors disabled:opacity-50"
        >
          Review
        </button>
        <button
          type="button"
          onClick={handleDisqualify}
          disabled={isLoading || (showReason && !reason.trim())}
          className="flex-1 px-3 py-1.5 text-xs font-medium rounded-md bg-error/15 text-error border border-error/30 hover:bg-error/25 transition-colors disabled:opacity-50"
        >
          Disqualify
        </button>
        {showReason && (
          <button
            type="button"
            onClick={() => { setShowReason(false); setReason('') }}
            className="px-2 py-1.5 text-xs text-text-dim hover:text-text"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  )
}

// ── Empty state ───────────────────────────────────────────

function TriageEmpty() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-12 h-12 rounded-full bg-success/10 flex items-center justify-center mb-4">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-success">
          <path d="M9 12l2 2 4-4" />
          <circle cx="12" cy="12" r="10" />
        </svg>
      </div>
      <p className="text-sm font-medium text-text-muted">Triage queue is empty</p>
      <p className="text-xs text-text-dim mt-1">All enriched companies have been reviewed. Run enrichment to add more.</p>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────

export function TriageReviewPage() {
  const [page, setPage] = useState(1)
  const { data, isLoading } = useTriageQueue(page)
  const triageMutation = useTriageCompany()
  const { toast } = useToast()

  const handleAction = useCallback(
    (companyId: string, action: TriageAction, reason?: string) => {
      triageMutation.mutate(
        { id: companyId, action, reason },
        {
          onSuccess: () => {
            const labels: Record<TriageAction, string> = {
              pass: 'passed',
              review: 'marked for review',
              disqualify: 'disqualified',
            }
            toast(`Company ${labels[action]}`, 'success')
          },
          onError: (err) => {
            toast(err instanceof Error ? err.message : 'Triage action failed', 'error')
          },
        },
      )
    },
    [triageMutation, toast],
  )

  const companies = data?.companies ?? []
  const total = data?.total ?? 0
  const pages = data?.pages ?? 1

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-text">Triage Review</h2>
          <p className="text-xs text-text-muted mt-0.5">
            {total} {total === 1 ? 'company' : 'companies'} pending review
          </p>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-surface rounded-lg border border-border p-4 h-40 animate-pulse" />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && companies.length === 0 && <TriageEmpty />}

      {/* Cards */}
      {!isLoading && companies.length > 0 && (
        <div className="space-y-3">
          {companies.map((company) => (
            <TriageCard
              key={company.id}
              company={company}
              onAction={handleAction}
              isLoading={triageMutation.isPending}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1.5 text-xs border border-border rounded-md hover:bg-surface-alt disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-xs text-text-muted tabular-nums">
            Page {page} of {pages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page >= pages}
            className="px-3 py-1.5 text-xs border border-border rounded-md hover:bg-surface-alt disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
