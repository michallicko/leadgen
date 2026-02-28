/**
 * Token Credits Dashboard — namespace admin view.
 *
 * Shows credit usage: budget gauge, usage by operation, usage over time,
 * and per-user breakdown. All values in credits — never USD.
 * Route: /:namespace/admin/tokens
 */

import { useEffect, useState, useMemo } from 'react'
import { useAuth } from '../../hooks/useAuth'
import { apiFetch } from '../../api/client'

// ── Types ────────────────────────────────────────────────────────────

interface ByOperation {
  operation: string
  calls: number
  credits: number
  pct: number
}

interface ByUser {
  user_id: string | null
  display_name: string
  credits: number
  pct: number
}

interface BudgetInfo {
  total_budget: number
  used_credits: number
  reserved_credits: number
  remaining_credits: number
  usage_pct: number
  reset_period: string | null
  reset_day: number
  enforcement_mode: string
  alert_threshold_pct: number
  next_reset_at: string | null
}

interface CurrentPeriod {
  start: string
  end: string
  total_calls: number
  total_credits: number
}

interface DashboardResponse {
  budget: BudgetInfo | null
  current_period: CurrentPeriod
  by_operation: ByOperation[]
  by_user: ByUser[]
}

interface HistoryPoint {
  date: string
  calls: number
  credits: number
}

interface HistoryResponse {
  period: string
  data: HistoryPoint[]
}

// ── Helpers ──────────────────────────────────────────────────────────

function formatCredits(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toLocaleString()
}

function formatOperation(op: string): string {
  return op
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function gaugeColor(pct: number): string {
  if (pct >= 95) return '#ef4444'   // red
  if (pct >= 80) return '#f97316'   // orange
  if (pct >= 60) return '#eab308'   // yellow
  return '#22c55e'                   // green
}

// ── Contextual grounding estimates ─────────────────────────────────

function estimateRemaining(remaining: number, byOp: ByOperation[]) {
  // Find the top-usage operation and estimate remaining count
  const estimates: { label: string; count: number }[] = []

  // Average credits per operation from actual data
  const chatOp = byOp.find((o) => o.operation === 'playbook_chat')
  if (chatOp && chatOp.calls > 0) {
    const avg = chatOp.credits / chatOp.calls
    if (avg > 0) estimates.push({ label: 'chat messages', count: Math.floor(remaining / avg) })
  }

  const l2Op = byOp.find((o) => o.operation.includes('l2'))
  if (l2Op && l2Op.calls > 0) {
    const avg = l2Op.credits / l2Op.calls
    if (avg > 0) estimates.push({ label: 'L2 enrichments', count: Math.floor(remaining / avg) })
  }

  const genOp = byOp.find((o) => o.operation === 'message_generation')
  if (genOp && genOp.calls > 0) {
    const avg = genOp.credits / genOp.calls
    if (avg > 0) estimates.push({ label: 'messages', count: Math.floor(remaining / avg) })
  }

  // Fallback generic estimates if no real data
  if (estimates.length === 0) {
    estimates.push({ label: 'chat messages', count: Math.floor(remaining / 10) })
    estimates.push({ label: 'L2 enrichments', count: Math.floor(remaining / 1000) })
  }

  // Return the most relevant (highest usage category)
  return estimates.sort((a, b) => {
    // Prefer estimates with reasonable counts
    if (a.count > 0 && b.count === 0) return -1
    if (a.count === 0 && b.count > 0) return 1
    return a.count - b.count
  })[0]
}

// ── Component ────────────────────────────────────────────────────────

export function TokensPage() {
  const { hasRole } = useAuth()

  const [data, setData] = useState<DashboardResponse | null>(null)
  const [history, setHistory] = useState<HistoryPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const isAdmin = hasRole('admin')

  useEffect(() => {
    if (!isAdmin) return

    let cancelled = false

    Promise.all([
      apiFetch<DashboardResponse>('/admin/tokens'),
      apiFetch<HistoryResponse>('/admin/tokens/history'),
    ])
      .then(([dashboard, hist]) => {
        if (!cancelled) {
          setData(dashboard)
          setHistory(hist.data)
          setError(null)
          setLoading(false)
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message)
          setLoading(false)
        }
      })

    return () => { cancelled = true }
  }, [isAdmin])

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-text-muted text-sm">Admin access required.</p>
      </div>
    )
  }

  return (
    <div className="max-w-[1060px] mx-auto">
      <div className="mb-5">
        <h1 className="font-title text-[1.3rem] font-semibold tracking-tight mb-1.5">
          Credits
        </h1>
        <p className="text-text-muted text-sm">
          Token credit usage and budget for your workspace.
        </p>
      </div>

      {loading && <LoadingSkeleton />}

      {!loading && error && (
        <div className="bg-surface border border-border rounded-lg p-8 text-center">
          <p className="text-error text-sm mb-3">Failed to load credit data: {error}</p>
        </div>
      )}

      {!loading && !error && data && (
        <>
          {/* Budget gauge + summary cards */}
          {data.budget ? (
            <BudgetSection budget={data.budget} byOp={data.by_operation} />
          ) : (
            <div className="bg-surface border border-border rounded-lg p-5 mb-6">
              <p className="text-text-muted text-sm">
                No budget configured — all operations monitored but unlimited.
              </p>
              <div className="mt-3 grid grid-cols-2 gap-4">
                <SummaryCard label="Credits Used" value={formatCredits(data.current_period.total_credits)} />
                <SummaryCard label="API Calls" value={data.current_period.total_calls.toLocaleString()} />
              </div>
            </div>
          )}

          {/* Usage over time */}
          {history.length > 0 && (
            <div className="bg-surface border border-border rounded-lg p-5 mb-6">
              <h2 className="font-title text-[1rem] font-semibold tracking-tight mb-4">
                Daily Usage
              </h2>
              <CreditChart data={history} />
            </div>
          )}

          {/* Usage by operation */}
          {data.by_operation.length > 0 && (
            <div className="bg-surface border border-border rounded-lg p-5 mb-6">
              <h2 className="font-title text-[1rem] font-semibold tracking-tight mb-4">
                Usage by Operation
              </h2>
              <OperationTable rows={data.by_operation} total={data.current_period.total_credits} />
            </div>
          )}

          {/* Usage by user */}
          {data.by_user.length > 1 && (
            <div className="bg-surface border border-border rounded-lg p-5 mb-6">
              <h2 className="font-title text-[1rem] font-semibold tracking-tight mb-4">
                Top Consumers
              </h2>
              <UserTable rows={data.by_user} />
            </div>
          )}

          {/* Empty state */}
          {data.current_period.total_calls === 0 && (
            <div className="bg-surface border border-border rounded-lg p-8 text-center text-text-muted">
              <div className="text-2xl mb-2">--</div>
              <div className="text-[0.85rem]">No credit usage recorded this period.</div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Sub-components ───────────────────────────────────────────────────

function BudgetSection({ budget, byOp }: { budget: BudgetInfo; byOp: ByOperation[] }) {
  const pct = budget.usage_pct
  const color = gaugeColor(pct)
  const estimate = estimateRemaining(budget.remaining_credits, byOp)

  // Days until reset
  let daysLeft: number | null = null
  if (budget.next_reset_at) {
    const resetDate = new Date(budget.next_reset_at)
    const now = new Date()
    daysLeft = Math.max(0, Math.ceil((resetDate.getTime() - now.getTime()) / 86400000))
  }

  return (
    <div className="bg-surface border border-border rounded-lg p-5 mb-6">
      <div className="flex flex-col sm:flex-row gap-6 items-start">
        {/* Gauge */}
        <div className="flex flex-col items-center gap-2 min-w-[140px]">
          <svg viewBox="0 0 120 120" className="w-[120px] h-[120px]">
            {/* Background circle */}
            <circle
              cx="60" cy="60" r="50"
              fill="none" stroke="currentColor" strokeWidth="10"
              className="text-surface-alt"
            />
            {/* Progress arc */}
            <circle
              cx="60" cy="60" r="50"
              fill="none" stroke={color} strokeWidth="10"
              strokeDasharray={`${Math.min(pct, 100) * 3.14} 314`}
              strokeLinecap="round"
              transform="rotate(-90 60 60)"
              className="transition-all duration-500"
            />
            {/* Center text */}
            <text x="60" y="55" textAnchor="middle" className="fill-text text-[1.4rem] font-semibold">
              {Math.round(pct)}%
            </text>
            <text x="60" y="72" textAnchor="middle" className="fill-text-muted text-[0.6rem]">
              used
            </text>
          </svg>

          {/* Contextual grounding */}
          {estimate && budget.remaining_credits > 0 && (
            <p className="text-[0.72rem] text-text-muted text-center">
              ~{estimate.count.toLocaleString()} {estimate.label} remaining
            </p>
          )}
        </div>

        {/* Summary cards */}
        <div className="flex-1 grid grid-cols-2 gap-3">
          <SummaryCard label="Credits Used" value={formatCredits(budget.used_credits)} />
          <SummaryCard label="Remaining" value={formatCredits(budget.remaining_credits)} />
          <SummaryCard label="Total Budget" value={formatCredits(budget.total_budget)} />
          <SummaryCard
            label="Resets In"
            value={daysLeft !== null ? `${daysLeft} days` : '--'}
            sub={budget.reset_period ?? 'No reset'}
          />
        </div>
      </div>
    </div>
  )
}

function SummaryCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-surface border border-border rounded-lg p-3">
      <dt className="text-text-muted text-[0.72rem] mb-0.5">{label}</dt>
      <dd className="text-[1.05rem] font-semibold text-text tabular-nums">{value}</dd>
      {sub && <dd className="text-[0.68rem] text-text-muted mt-0.5">{sub}</dd>}
    </div>
  )
}

function OperationTable({ rows, total }: { rows: ByOperation[]; total: number }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-text-muted text-[0.75rem]">
            <th className="pb-2 pr-4 font-medium">Operation</th>
            <th className="pb-2 pr-4 font-medium text-right">Calls</th>
            <th className="pb-2 pr-4 font-medium text-right">Credits</th>
            <th className="pb-2 font-medium w-[120px]">Share</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const pct = total > 0 ? (r.credits / total) * 100 : 0
            return (
              <tr key={r.operation} className="border-b border-border/50 last:border-0">
                <td className="py-2 pr-4 text-text">{formatOperation(r.operation)}</td>
                <td className="py-2 pr-4 text-right text-text tabular-nums">
                  {r.calls.toLocaleString()}
                </td>
                <td className="py-2 pr-4 text-right text-text font-medium tabular-nums">
                  {formatCredits(r.credits)}
                </td>
                <td className="py-2">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-surface-alt rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent rounded-full"
                        style={{ width: `${Math.max(pct, 1)}%` }}
                      />
                    </div>
                    <span className="text-[0.7rem] text-text-muted w-[36px] text-right tabular-nums">
                      {pct.toFixed(0)}%
                    </span>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function UserTable({ rows }: { rows: ByUser[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-text-muted text-[0.75rem]">
            <th className="pb-2 pr-4 font-medium">User</th>
            <th className="pb-2 pr-4 font-medium text-right">Credits</th>
            <th className="pb-2 font-medium text-right">Share</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.user_id ?? 'system'} className="border-b border-border/50 last:border-0">
              <td className="py-2 pr-4 text-text">{r.display_name}</td>
              <td className="py-2 pr-4 text-right text-text font-medium tabular-nums">
                {formatCredits(r.credits)}
              </td>
              <td className="py-2 text-right text-text-muted text-[0.8rem] tabular-nums">
                {r.pct.toFixed(0)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CreditChart({ data }: { data: HistoryPoint[] }) {
  const maxCredits = useMemo(
    () => Math.max(...data.map((p) => p.credits), 1),
    [data],
  )

  return (
    <div className="flex items-end gap-[3px] h-[120px]">
      {data.map((point) => {
        const heightPct = (point.credits / maxCredits) * 100
        const dateLabel = new Date(point.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
        return (
          <div
            key={point.date}
            className="flex-1 flex flex-col items-center justify-end h-full group relative"
          >
            <div className="absolute bottom-full mb-1 hidden group-hover:block bg-surface border border-border rounded px-2 py-1 text-[0.7rem] text-text shadow-md whitespace-nowrap z-10">
              <div className="font-medium">{dateLabel}</div>
              <div>{formatCredits(point.credits)} credits / {point.calls} calls</div>
            </div>
            <div
              className="w-full bg-accent/70 hover:bg-accent rounded-t transition-colors"
              style={{
                height: `${Math.max(heightPct, 2)}%`,
                minHeight: '2px',
              }}
            />
          </div>
        )
      })}
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="bg-surface border border-border rounded-lg p-5 mb-6">
        <div className="flex gap-6">
          <div className="w-[120px] h-[120px] bg-surface-alt rounded-full" />
          <div className="flex-1 grid grid-cols-2 gap-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="bg-surface-alt rounded-lg h-16" />
            ))}
          </div>
        </div>
      </div>
      <div className="bg-surface border border-border rounded-lg p-5 mb-6">
        <div className="h-4 w-24 bg-surface-alt rounded mb-4" />
        <div className="h-[120px] bg-surface-alt rounded" />
      </div>
    </div>
  )
}
