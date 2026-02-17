/**
 * RunHistoryPanel — compact list of previous pipeline runs below the DAG.
 * Shows date, duration, stages run, cost, status. Click opens RunResultsModal.
 */

import { useRunHistory, type PipelineRun } from './useRunHistory'

interface RunHistoryPanelProps {
  batchName: string
  onSelectRun: (run: PipelineRun) => void
}

const STATUS_BADGE: Record<string, string> = {
  completed: 'bg-success/15 text-success border-success/30',
  failed: 'bg-error/15 text-error border-error/30',
  running: 'bg-[#00B8CF]/15 text-[#00B8CF] border-[#00B8CF]/30',
  stopped: 'bg-[#8B92A0]/10 text-text-muted border-[#8B92A0]/20',
}

function fmtDuration(s: number | null): string {
  if (s === null) return '-'
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const sec = s % 60
  return sec > 0 ? `${m}m ${sec}s` : `${m}m`
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

export function RunHistoryPanel({ batchName, onSelectRun }: RunHistoryPanelProps) {
  const { data, isLoading } = useRunHistory(batchName)

  if (isLoading) {
    return (
      <div className="mt-6 flex items-center gap-2 text-sm text-text-muted">
        <div className="w-4 h-4 border-2 border-border border-t-accent rounded-full animate-spin" />
        Loading run history...
      </div>
    )
  }

  if (!data?.runs.length) {
    return (
      <div className="mt-6">
        <h3 className="text-sm font-semibold text-text-muted mb-2">Run History</h3>
        <p className="text-sm text-text-dim">No previous runs for this batch.</p>
      </div>
    )
  }

  return (
    <div className="mt-6">
      <h3 className="text-sm font-semibold text-text-muted mb-2">
        Run History
        <span className="ml-1 text-text-dim font-normal">({data.total})</span>
      </h3>

      <div className="space-y-1">
        {data.runs.map((run) => {
          const badge = STATUS_BADGE[run.status] ?? STATUS_BADGE.stopped
          return (
            <button
              key={run.id}
              onClick={() => onSelectRun(run)}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg border border-border/40 bg-surface hover:bg-surface-alt/50 transition-colors text-left"
            >
              <span className="text-xs text-text-muted whitespace-nowrap min-w-[100px]">
                {fmtDate(run.started_at)}
              </span>
              <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border whitespace-nowrap ${badge}`}>
                {run.status}
              </span>
              <span className="text-xs text-text-muted">
                {run.stages.join(', ')}
              </span>
              <span className="ml-auto text-xs text-text-dim whitespace-nowrap">
                {fmtDuration(run.duration_s)}
              </span>
              <span className="text-xs text-text-muted whitespace-nowrap">
                {fmtCost(run.cost)}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
