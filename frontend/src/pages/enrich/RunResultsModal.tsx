/**
 * RunResultsModal — shows per-entity results for a pipeline run.
 * Tabs for each stage, summary stats at top.
 */

import { useState } from 'react'
import { LargeModal } from '../../components/ui/LargeModal'
import { EntityResultsTable } from '../../components/ui/EntityResultsTable'
import { useRunEntities, type PipelineRun } from './useRunHistory'

interface RunResultsModalProps {
  isOpen: boolean
  onClose: () => void
  run: PipelineRun
  initialStage?: string
  initialStatus?: string
}

function fmtDate(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function fmtCost(v: number): string {
  if (v === 0) return 'free'
  if (v < 0.01) return `$${v.toFixed(4)}`
  return `$${v.toFixed(2)}`
}

export function RunResultsModal({
  isOpen,
  onClose,
  run,
  initialStage,
  initialStatus,
}: RunResultsModalProps) {
  const [activeStage, setActiveStage] = useState(initialStage ?? '')
  const [statusFilter, setStatusFilter] = useState(initialStatus ?? '')

  const { data, isLoading } = useRunEntities(
    run.id,
    activeStage || undefined,
    statusFilter || undefined,
  )

  return (
    <LargeModal
      isOpen={isOpen}
      onClose={onClose}
      title={`Run Results`}
      subtitle={`${fmtDate(run.started_at)} — ${run.status} — ${fmtCost(run.cost)}`}
    >
      {/* Stage tabs */}
      <div className="flex items-center gap-1 mb-3 flex-wrap">
        <button
          onClick={() => setActiveStage('')}
          className={`px-3 py-1 text-xs font-medium rounded-full border transition-colors ${
            !activeStage
              ? 'border-accent bg-accent/10 text-accent'
              : 'border-border text-text-muted hover:border-accent/40'
          }`}
        >
          All
        </button>
        {run.stages.map((stage) => (
          <button
            key={stage}
            onClick={() => setActiveStage(stage)}
            className={`px-3 py-1 text-xs font-medium rounded-full border transition-colors ${
              activeStage === stage
                ? 'border-accent bg-accent/10 text-accent'
                : 'border-border text-text-muted hover:border-accent/40'
            }`}
          >
            {stage}
          </button>
        ))}
      </div>

      {/* Status filter */}
      <div className="flex items-center gap-1 mb-4">
        {['', 'completed', 'failed'].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-2.5 py-0.5 text-xs rounded border transition-colors ${
              statusFilter === s
                ? 'border-accent bg-accent/10 text-accent'
                : 'border-border text-text-muted hover:border-accent/40'
            }`}
          >
            {s || 'All statuses'}
          </button>
        ))}
      </div>

      {/* Results count */}
      {data && (
        <p className="text-xs text-text-dim mb-2">
          {data.total} result{data.total !== 1 ? 's' : ''}
        </p>
      )}

      <EntityResultsTable
        results={data?.entities ?? []}
        isLoading={isLoading}
        emptyText="No entity results for this run."
      />
    </LargeModal>
  )
}
