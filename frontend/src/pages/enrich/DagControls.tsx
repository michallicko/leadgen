/**
 * DagControls — top bar with tag info, total cost, config manager, and run/stop buttons.
 */

import type { DagMode } from './StageCard.types'
import { ConfigManager } from './ConfigManager'

interface DagControlsProps {
  mode: DagMode
  tagName: string
  estimatedCost: number
  runningCost: number
  enabledCount: number
  onRun: () => void
  onStop: () => void
  isLoading: boolean
  onLoadConfig?: (config: Record<string, unknown>) => void
  getConfigSnapshot?: () => Record<string, unknown>
}

function fmtCost(v: number): string {
  if (v === 0) return '$0.00'
  if (v < 0.01) return `$${v.toFixed(4)}`
  return `$${v.toFixed(2)}`
}

export function DagControls({
  mode,
  tagName,
  estimatedCost,
  runningCost,
  enabledCount,
  onRun,
  onStop,
  isLoading,
  onLoadConfig,
  getConfigSnapshot,
}: DagControlsProps) {
  return (
    <div className="flex items-center justify-between mb-4 px-1">
      {/* Left: tag info + cost */}
      <div className="flex items-center gap-4">
        {tagName && (
          <span className="text-sm text-text">
            <span className="text-text-muted">Tag:</span>{' '}
            <span className="font-medium">{tagName}</span>
          </span>
        )}

        {mode === 'configure' && estimatedCost > 0 && (
          <span className="text-sm text-text-muted">
            Est. cost: <span className="font-medium text-text">{fmtCost(estimatedCost)}</span>
          </span>
        )}

        {(mode === 'running' || mode === 'completed') && (
          <span className="text-sm text-text-muted">
            Cost: <span className="font-medium text-text">{fmtCost(runningCost)}</span>
          </span>
        )}
      </div>

      {/* Right: action buttons */}
      <div className="flex items-center gap-2">
        {mode === 'configure' && (
          <>
            {onLoadConfig && getConfigSnapshot && (
              <ConfigManager onLoad={onLoadConfig} getSnapshot={getConfigSnapshot} />
            )}
            <button
              onClick={onRun}
              disabled={enabledCount === 0 || !tagName || isLoading}
              className="px-4 py-1.5 text-sm font-medium rounded-md bg-accent text-white hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? 'Loading...' : `Run ${enabledCount} stage${enabledCount !== 1 ? 's' : ''}`}
            </button>
          </>
        )}

        {mode === 'running' && (
          <>
            <span className="flex items-center gap-2 text-sm text-accent-cyan">
              <span className="inline-block w-3 h-3 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
              Pipeline running...
            </span>
            <button
              onClick={onStop}
              className="px-3 py-1.5 text-sm font-medium rounded-md border border-error text-error hover:bg-error/10 transition-colors"
            >
              Stop All
            </button>
          </>
        )}
      </div>
    </div>
  )
}
