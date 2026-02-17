/**
 * CompletionPanel — shown after pipeline completes.
 * Displays summary stats and a button to configure a new run.
 */

import type { StageProgress } from './StageCard.types'

interface CompletionPanelProps {
  stageProgress: Record<string, StageProgress>
  totalCost: number
  onReset: () => void
}

function fmtCost(v: number): string {
  if (v === 0) return '$0.00'
  if (v < 0.01) return `$${v.toFixed(4)}`
  return `$${v.toFixed(2)}`
}

export function CompletionPanel({ stageProgress, totalCost, onReset }: CompletionPanelProps) {
  const stages = Object.values(stageProgress)
  const totalDone = stages.reduce((sum, s) => sum + s.done, 0)
  const totalFailed = stages.reduce((sum, s) => sum + s.failed, 0)
  const allCompleted = stages.every((s) => s.status === 'completed')
  const hasFailed = stages.some((s) => s.status === 'failed')
  const wasStopped = stages.some((s) => s.status === 'stopped')

  const icon = allCompleted ? '\u2713' : hasFailed ? '\u2717' : '\u23F8'
  const iconColor = allCompleted ? 'text-success' : hasFailed ? 'text-error' : 'text-text-muted'
  const title = allCompleted
    ? 'Pipeline Complete'
    : wasStopped
      ? 'Pipeline Stopped'
      : 'Pipeline Finished with Errors'

  return (
    <div className="mt-6 p-4 rounded-lg border border-border bg-surface-alt">
      <div className="flex items-center gap-3 mb-3">
        <span className={`text-2xl ${iconColor}`}>{icon}</span>
        <h3 className="text-sm font-semibold text-text">{title}</h3>
      </div>

      <div className="flex gap-6 text-sm text-text-muted mb-4">
        <span>
          Processed: <span className="font-medium text-text">{totalDone}</span>
        </span>
        {totalFailed > 0 && (
          <span>
            Failed: <span className="font-medium text-error">{totalFailed}</span>
          </span>
        )}
        <span>
          Total cost: <span className="font-medium text-text">{fmtCost(totalCost)}</span>
        </span>
        <span>
          Stages: <span className="font-medium text-text">{stages.length}</span>
        </span>
      </div>

      <button
        onClick={onReset}
        className="px-4 py-1.5 text-sm font-medium rounded-md border border-accent text-accent hover:bg-accent/10 transition-colors"
      >
        Configure New Run
      </button>
    </div>
  )
}
