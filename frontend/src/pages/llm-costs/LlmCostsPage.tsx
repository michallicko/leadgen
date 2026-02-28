/**
 * LLM Costs Dashboard — super_admin only.
 *
 * Shows aggregated LLM usage: summary cards, breakdown by operation,
 * breakdown by model, and a daily cost bar chart.
 * Consumes GET /api/llm-usage/summary.
 */

import { useEffect, useState, useMemo } from 'react'
import { useAuth } from '../../hooks/useAuth'
import { apiFetch } from '../../api/client'

// ── Types ────────────────────────────────────────────────────────────

interface ByOperation {
  operation: string
  calls: number
  cost: number
  input_tokens: number
  output_tokens: number
}

interface ByModel {
  provider: string
  model: string
  calls: number
  cost: number
  input_tokens: number
  output_tokens: number
}

interface TimeSeriesPoint {
  period: string
  calls: number
  cost: number
  input_tokens: number
  output_tokens: number
}

interface SummaryResponse {
  total_cost_usd: number
  total_calls: number
  total_input_tokens: number
  total_output_tokens: number
  by_tenant: unknown[]
  by_operation: ByOperation[]
  by_model: ByModel[]
  time_series: TimeSeriesPoint[]
}

// ── Helpers ──────────────────────────────────────────────────────────

function formatUsd(n: number): string {
  return '$' + n.toFixed(4)
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toString()
}

function formatDateShort(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

/** Pretty-print operation name: snake_case -> Title Case */
function formatOperation(op: string): string {
  return op
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function daysAgo(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

// ── Component ────────────────────────────────────────────────────────

export function LlmCostsPage() {
  const { user } = useAuth()

  const [data, setData] = useState<SummaryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [startDate, setStartDate] = useState(daysAgo(30))
  const [endDate, setEndDate] = useState(daysAgo(0))
  const [fetchSeq, setFetchSeq] = useState(0)

  const isSuperAdmin = user?.is_super_admin ?? false

  // Wrap date setters to also trigger loading state
  function handleStartDate(v: string) {
    setStartDate(v)
    setLoading(true)
  }
  function handleEndDate(v: string) {
    setEndDate(v)
    setLoading(true)
  }

  useEffect(() => {
    if (!isSuperAdmin) return
    let cancelled = false
    apiFetch<SummaryResponse>('/llm-usage/summary', {
      params: { start_date: startDate, end_date: endDate },
    })
      .then((result) => {
        if (!cancelled) {
          setData(result)
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
  }, [startDate, endDate, fetchSeq, isSuperAdmin])

  // Super admin guard
  if (!isSuperAdmin) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-text-muted text-sm">Super admin access required.</p>
      </div>
    )
  }

  // Derived values
  const avgCost =
    data && data.total_calls > 0
      ? data.total_cost_usd / data.total_calls
      : 0

  const topOperation =
    data && data.by_operation.length > 0
      ? data.by_operation[0]
      : null

  return (
    <div className="max-w-[1060px] mx-auto">
      {/* Header */}
      <div className="mb-5">
        <h1 className="font-title text-[1.3rem] font-semibold tracking-tight mb-1.5">
          LLM Costs
        </h1>
        <p className="text-text-muted text-sm">
          AI usage tracking — cost breakdown, per-operation analysis, and daily trends.
        </p>
      </div>

      {/* Date range */}
      <div className="flex items-center gap-3 mb-5">
        <label className="text-sm text-text-muted">From</label>
        <input
          type="date"
          value={startDate}
          onChange={(e) => handleStartDate(e.target.value)}
          className="bg-surface border border-border rounded-md px-2 py-1 text-sm text-text"
        />
        <label className="text-sm text-text-muted">To</label>
        <input
          type="date"
          value={endDate}
          onChange={(e) => handleEndDate(e.target.value)}
          className="bg-surface border border-border rounded-md px-2 py-1 text-sm text-text"
        />
      </div>

      {/* Loading state */}
      {loading && <LoadingSkeleton />}

      {/* Error state */}
      {!loading && error && (
        <div className="bg-surface border border-border rounded-lg p-8 text-center">
          <p className="text-error text-sm mb-3">Failed to load cost data: {error}</p>
          <button
            onClick={() => { setLoading(true); setFetchSeq((c) => c + 1) }}
            className="text-sm text-accent hover:underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && data && data.total_calls === 0 && (
        <div className="bg-surface border border-border rounded-lg p-8 text-center text-text-muted">
          <div className="text-2xl mb-2">--</div>
          <div className="text-[0.85rem]">
            No LLM usage recorded for the selected period.
          </div>
        </div>
      )}

      {/* Data loaded */}
      {!loading && !error && data && data.total_calls > 0 && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <SummaryCard label="Total Cost" value={formatUsd(data.total_cost_usd)} />
            <SummaryCard label="API Calls" value={data.total_calls.toLocaleString()} />
            <SummaryCard label="Avg Cost / Call" value={formatUsd(avgCost)} />
            <SummaryCard
              label="Top Operation"
              value={topOperation ? formatOperation(topOperation.operation) : '--'}
              sub={topOperation ? `${formatUsd(topOperation.cost)} (${topOperation.calls} calls)` : undefined}
            />
          </div>

          {/* Daily cost chart */}
          {data.time_series.length > 0 && (
            <div className="bg-surface border border-border rounded-lg p-5 mb-6">
              <h2 className="font-title text-[1rem] font-semibold tracking-tight mb-4">
                Daily Cost
              </h2>
              <DailyCostChart timeSeries={data.time_series} />
            </div>
          )}

          {/* Breakdown by operation */}
          <div className="bg-surface border border-border rounded-lg p-5 mb-6">
            <h2 className="font-title text-[1rem] font-semibold tracking-tight mb-4">
              Cost by Operation
            </h2>
            <BreakdownTable
              rows={data.by_operation.map((r) => ({
                label: formatOperation(r.operation),
                calls: r.calls,
                inputTokens: r.input_tokens,
                outputTokens: r.output_tokens,
                cost: r.cost,
              }))}
              totalCost={data.total_cost_usd}
            />
          </div>

          {/* Breakdown by model */}
          <div className="bg-surface border border-border rounded-lg p-5 mb-6">
            <h2 className="font-title text-[1rem] font-semibold tracking-tight mb-4">
              Cost by Model
            </h2>
            <BreakdownTable
              rows={data.by_model.map((r) => ({
                label: `${r.provider} / ${r.model}`,
                calls: r.calls,
                inputTokens: r.input_tokens,
                outputTokens: r.output_tokens,
                cost: r.cost,
              }))}
              totalCost={data.total_cost_usd}
            />
          </div>
        </>
      )}
    </div>
  )
}

// ── Sub-components ───────────────────────────────────────────────────

function SummaryCard({
  label,
  value,
  sub,
}: {
  label: string
  value: string
  sub?: string
}) {
  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      <dt className="text-text-muted text-[0.75rem] mb-1">{label}</dt>
      <dd className="text-[1.15rem] font-semibold text-text">{value}</dd>
      {sub && <dd className="text-[0.72rem] text-text-muted mt-0.5">{sub}</dd>}
    </div>
  )
}

interface BreakdownRow {
  label: string
  calls: number
  inputTokens: number
  outputTokens: number
  cost: number
}

function BreakdownTable({
  rows,
  totalCost,
}: {
  rows: BreakdownRow[]
  totalCost: number
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-text-muted text-[0.75rem]">
            <th className="pb-2 pr-4 font-medium">Name</th>
            <th className="pb-2 pr-4 font-medium text-right">Calls</th>
            <th className="pb-2 pr-4 font-medium text-right">Input Tokens</th>
            <th className="pb-2 pr-4 font-medium text-right">Output Tokens</th>
            <th className="pb-2 pr-4 font-medium text-right">Cost</th>
            <th className="pb-2 font-medium w-[120px]">Share</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const pct = totalCost > 0 ? (r.cost / totalCost) * 100 : 0
            return (
              <tr key={r.label} className="border-b border-border/50 last:border-0">
                <td className="py-2 pr-4 text-text">{r.label}</td>
                <td className="py-2 pr-4 text-right text-text tabular-nums">
                  {r.calls.toLocaleString()}
                </td>
                <td className="py-2 pr-4 text-right text-text-muted tabular-nums">
                  {formatTokens(r.inputTokens)}
                </td>
                <td className="py-2 pr-4 text-right text-text-muted tabular-nums">
                  {formatTokens(r.outputTokens)}
                </td>
                <td className="py-2 pr-4 text-right text-text font-medium tabular-nums">
                  {formatUsd(r.cost)}
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

function DailyCostChart({ timeSeries }: { timeSeries: TimeSeriesPoint[] }) {
  const maxCost = useMemo(
    () => Math.max(...timeSeries.map((p) => p.cost), 0.0001),
    [timeSeries],
  )

  return (
    <div className="flex items-end gap-[3px] h-[120px]">
      {timeSeries.map((point) => {
        const heightPct = (point.cost / maxCost) * 100
        return (
          <div
            key={point.period}
            className="flex-1 flex flex-col items-center justify-end h-full group relative"
          >
            {/* Tooltip */}
            <div className="absolute bottom-full mb-1 hidden group-hover:block bg-surface border border-border rounded px-2 py-1 text-[0.7rem] text-text shadow-md whitespace-nowrap z-10">
              <div className="font-medium">{formatDateShort(point.period)}</div>
              <div>{formatUsd(point.cost)} / {point.calls} calls</div>
            </div>
            {/* Bar */}
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
      {/* Summary cards skeleton */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-surface border border-border rounded-lg p-4">
            <div className="h-3 w-16 bg-surface-alt rounded mb-2" />
            <div className="h-5 w-24 bg-surface-alt rounded" />
          </div>
        ))}
      </div>
      {/* Chart skeleton */}
      <div className="bg-surface border border-border rounded-lg p-5 mb-6">
        <div className="h-4 w-24 bg-surface-alt rounded mb-4" />
        <div className="h-[120px] bg-surface-alt rounded" />
      </div>
      {/* Table skeleton */}
      <div className="bg-surface border border-border rounded-lg p-5 mb-6">
        <div className="h-4 w-32 bg-surface-alt rounded mb-4" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-8 bg-surface-alt rounded" />
          ))}
        </div>
      </div>
    </div>
  )
}
