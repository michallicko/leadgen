/**
 * CostEstimator — reusable credit cost preview component.
 *
 * Shows per-stage costs, total estimated credits, and remaining budget
 * before the user triggers an enrichment or generation operation.
 *
 * Props:
 * - tagName: batch/tag to estimate for
 * - stages: enrichment stages to include (e.g. ['l1', 'l2', 'person'])
 * - contactCount: optional display hint for selected contacts
 * - compact: if true, renders a single-line summary instead of full breakdown
 */

import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'
import { useTokenBudget } from '../../hooks/useTokenBudget'

// ── Types ────────────────────────────────────────────────────

interface StageEstimate {
  eligible_count: number
  cost_per_item: number
  estimated_cost: number
  fields: string[]
}

interface EstimateResponse {
  stages: Record<string, StageEstimate>
  total_estimated_cost: number
}

interface CostEstimatorProps {
  tagName: string
  stages: string[]
  ownerName?: string
  contactCount?: number
  compact?: boolean
  className?: string
}

// ── Stage display names ──────────────────────────────────────

const STAGE_LABELS: Record<string, string> = {
  l1: 'L1 Company',
  l2: 'L2 Company',
  signals: 'Signals',
  registry: 'Registry',
  news: 'News',
  person: 'Person',
  social: 'Social',
  career: 'Career',
  contact_details: 'Contact Details',
  qc: 'QC',
}

// ── Hook ─────────────────────────────────────────────────────

function useCostEstimate(tagName: string, stages: string[], ownerName?: string) {
  return useQuery({
    queryKey: ['cost-estimate', tagName, stages, ownerName],
    queryFn: () => {
      const body: Record<string, unknown> = {
        tag_name: tagName,
        stages,
      }
      if (ownerName) body.owner_name = ownerName
      return apiFetch<EstimateResponse>('/enrich/estimate', {
        method: 'POST',
        body,
      })
    },
    enabled: !!tagName && stages.length > 0,
    staleTime: 15_000,
  })
}

// ── Component ────────────────────────────────────────────────

export function CostEstimator({
  tagName,
  stages,
  ownerName,
  contactCount,
  compact = false,
  className = '',
}: CostEstimatorProps) {
  const estimate = useCostEstimate(tagName, stages, ownerName)
  const { budget } = useTokenBudget()

  const totalCost = estimate.data?.total_estimated_cost ?? 0
  const stageData = estimate.data?.stages ?? {}
  const remaining = budget?.remaining_credits ?? null

  const creditsCost = useMemo(() => {
    // Convert USD to credits (1 credit = $0.001)
    return Math.ceil(totalCost / 0.001)
  }, [totalCost])

  const willExceedBudget = remaining !== null && creditsCost > remaining

  if (!tagName || stages.length === 0) {
    return null
  }

  if (estimate.isLoading) {
    return (
      <div className={`flex items-center gap-2 text-xs text-text-dim ${className}`}>
        <div className="w-3 h-3 border border-border border-t-accent-cyan rounded-full animate-spin" />
        Estimating cost...
      </div>
    )
  }

  if (estimate.isError) {
    return (
      <div className={`text-xs text-text-dim ${className}`}>
        Cost estimate unavailable
      </div>
    )
  }

  // Compact mode: single line
  if (compact) {
    return (
      <div className={`flex items-center gap-2 text-xs ${className}`}>
        <span className="text-text-muted">Est. cost:</span>
        <span className={`font-medium ${willExceedBudget ? 'text-error' : 'text-text'}`}>
          {creditsCost.toLocaleString()} credits
        </span>
        {remaining !== null && (
          <span className="text-text-dim">
            / {remaining.toLocaleString()} remaining
          </span>
        )}
        {willExceedBudget && (
          <span className="text-error text-[10px]">
            (exceeds budget)
          </span>
        )}
      </div>
    )
  }

  // Full breakdown
  return (
    <div className={`rounded-lg border border-border bg-surface-alt/50 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
        <span className="text-xs font-semibold text-text-dim uppercase tracking-wider">
          Cost Estimate
        </span>
        {contactCount != null && contactCount > 0 && (
          <span className="text-xs text-text-muted">
            {contactCount.toLocaleString()} contact{contactCount !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Stage rows */}
      <div className="px-4 py-2 space-y-1.5">
        {Object.entries(stageData).map(([code, est]) => (
          <div key={code} className="flex items-center justify-between">
            <span className="text-xs text-text-muted">
              {STAGE_LABELS[code] || code}
              <span className="text-text-dim ml-1.5">
                ({est.eligible_count} item{est.eligible_count !== 1 ? 's' : ''})
              </span>
            </span>
            <span className="text-xs tabular-nums text-text">
              {Math.ceil(est.estimated_cost / 0.001).toLocaleString()} cr
            </span>
          </div>
        ))}
      </div>

      {/* Total + budget */}
      <div className="flex items-center justify-between px-4 py-2.5 border-t border-border">
        <span className="text-xs font-semibold text-text">Total</span>
        <div className="text-right">
          <span className={`text-sm font-semibold tabular-nums ${willExceedBudget ? 'text-error' : 'text-text'}`}>
            {creditsCost.toLocaleString()} credits
          </span>
          {remaining !== null && (
            <div className="text-[10px] text-text-dim mt-0.5">
              {remaining.toLocaleString()} credits remaining
              {willExceedBudget && (
                <span className="text-error ml-1">-- insufficient</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
