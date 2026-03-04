/**
 * CompletionPanel — shown after pipeline completes.
 * Displays summary stats, a button to configure a new run,
 * and an auto-setup campaign button (BL-147).
 */

import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useAutoSetupCampaign, type AutoSetupResult } from '../../api/queries/useCampaigns'
import { useToast } from '../../components/ui/Toast'
import type { StageProgress } from './StageCard.types'

interface CompletionPanelProps {
  stageProgress: Record<string, StageProgress>
  totalCost: number
  onReset: () => void
}

function fmtCost(v: number): string {
  const credits = Math.round(v * 1000)
  if (credits === 0) return '0 credits'
  return `${credits} credits`
}

export function CompletionPanel({ stageProgress, totalCost, onReset }: CompletionPanelProps) {
  const { namespace } = useParams<{ namespace: string }>()
  const navigate = useNavigate()
  const autoSetup = useAutoSetupCampaign()
  const { toast } = useToast()
  const [setupResult, setSetupResult] = useState<AutoSetupResult | null>(null)

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

  const handleAutoSetup = async () => {
    try {
      const result = await autoSetup.mutateAsync({})
      setSetupResult(result)
      toast(
        `Campaign "${result.name}" created with ${result.total_contacts} contacts`,
        'success',
      )
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create campaign'
      toast(msg, 'error')
    }
  }

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

      {/* Auto-setup campaign result (BL-147) */}
      {setupResult && (
        <div className="mb-4 p-3 rounded-md border border-success/30 bg-success/5">
          <p className="text-sm font-medium text-text mb-1">
            Campaign created: {setupResult.name}
          </p>
          <p className="text-xs text-text-muted mb-2">
            {setupResult.total_contacts} contacts
            {setupResult.with_email > 0 && ` | ${setupResult.with_email} with email`}
            {setupResult.with_linkedin > 0 && ` | ${setupResult.with_linkedin} with LinkedIn`}
            {setupResult.strategy_prefilled && ' | Pre-filled from GTM Strategy'}
          </p>
          <button
            onClick={() => navigate(`/${namespace}/campaigns/${setupResult.id}`)}
            className="px-3 py-1 text-xs font-medium rounded-md bg-accent text-white hover:bg-accent-hover transition-colors"
          >
            Review Campaign
          </button>
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={onReset}
          className="px-4 py-1.5 text-sm font-medium rounded-md border border-accent text-accent hover:bg-accent/10 transition-colors"
        >
          Configure New Run
        </button>

        {/* Auto-setup campaign button (BL-147) */}
        {!setupResult && (
          <button
            onClick={handleAutoSetup}
            disabled={autoSetup.isPending}
            className="px-4 py-1.5 text-sm font-medium rounded-md bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
          >
            {autoSetup.isPending ? 'Creating...' : 'Create Campaign from Qualified Contacts'}
          </button>
        )}
      </div>
    </div>
  )
}
