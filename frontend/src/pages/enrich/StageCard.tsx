/**
 * StageCard — self-contained DAG node card for a single enrichment stage.
 * Renders differently based on DagMode: configure (toggle, estimate, re-enrich)
 * vs running (progress bar, cost) vs completed (final stats).
 */

import { useState } from 'react'
import type { StageDef } from './stageConfig'
import type { StageEstimate, StageProgress, ReEnrichConfig, DagMode } from './StageCard.types'

interface StageCardProps {
  stage: StageDef
  mode: DagMode
  estimate: StageEstimate | null
  enabled: boolean
  onToggle: (enabled: boolean) => void
  progress: StageProgress | null
  softDeps: { code: string; name: string; active: boolean }[]
  onSoftDepToggle: (dep: string, active: boolean) => void
  reEnrich: ReEnrichConfig
  onReEnrichToggle: (enabled: boolean) => void
  onFreshnessChange: (horizon: string | null) => void
}

const HORIZON_PRESETS = [
  { label: '7d', days: 7 },
  { label: '14d', days: 14 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
]

function horizonToDate(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString()
}

function fmtCost(v: number): string {
  if (v === 0) return 'free'
  if (v < 0.01) return `$${v.toFixed(4)}`
  return `$${v.toFixed(2)}`
}

export function StageCard({
  stage,
  mode,
  estimate,
  enabled,
  onToggle,
  progress,
  softDeps,
  onSoftDepToggle,
  reEnrich,
  onReEnrichToggle,
  onFreshnessChange,
}: StageCardProps) {
  const [showFailed, setShowFailed] = useState(false)
  const isRunning = mode === 'running'
  const isCompleted = mode === 'completed'

  const isGate = !!stage.isGate

  // Card visual state
  const statusClass = (() => {
    if (!enabled && mode === 'configure') return 'opacity-40'
    if (isRunning && progress) {
      if (progress.status === 'running')
        return 'border-[color:var(--color-accent-cyan)] shadow-[0_0_16px_-4px_rgba(0,184,207,0.4)]'
      if (progress.status === 'completed') return 'border-success'
      if (progress.status === 'failed') return 'border-error'
    }
    if (isCompleted && progress) {
      if (progress.status === 'completed') return 'border-success'
      if (progress.status === 'failed') return 'border-error'
    }
    if (enabled && mode === 'configure') {
      if (isGate) return 'border-[color:#06d6a0]/40 ring-1 ring-[color:#06d6a0]/10'
      return 'border-accent/40 ring-1 ring-accent/10'
    }
    return 'border-dashed border-border-solid'
  })()

  // Status icon for running mode
  const statusIcon = (() => {
    if (!progress) return null
    if (progress.status === 'running')
      return (
        <span className="inline-block w-3 h-3 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
      )
    if (progress.status === 'completed')
      return <span className="text-success text-xs">&#10003;</span>
    if (progress.status === 'failed')
      return <span className="text-error text-xs">&#10007;</span>
    if (progress.status === 'stopped')
      return <span className="text-text-muted text-xs">&#9632;</span>
    return null
  })()

  const pctDone = progress && progress.total > 0
    ? Math.round((progress.done / progress.total) * 100)
    : 0

  return (
    <div
      className={`rounded-lg border bg-surface p-4 transition-all duration-200 flex-shrink-0 ${isGate ? 'w-[200px]' : 'w-[280px]'} ${statusClass}`}
      style={{ borderColor: enabled && mode === 'configure' ? stage.color : undefined }}
    >
      {/* Header: icon + name + toggle/status */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span
            className="inline-flex items-center justify-center w-7 h-7 rounded text-[0.65rem] font-bold text-white"
            style={{ backgroundColor: stage.color }}
          >
            {stage.icon}
          </span>
          <span className="text-sm font-semibold text-text">{stage.displayName}</span>
        </div>

        {mode === 'configure' ? (
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => onToggle(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-8 h-[18px] bg-border-solid rounded-full peer peer-checked:bg-accent transition-colors after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-[14px] after:w-[14px] after:transition-all peer-checked:after:translate-x-[14px]" />
          </label>
        ) : (
          statusIcon
        )}
      </div>

      {/* Configure mode content */}
      {mode === 'configure' && (
        <>
          {/* Description */}
          <p className="text-xs text-text-muted italic mb-2 leading-relaxed">
            {stage.description}
          </p>

          {isGate ? (
            /* Gate cards: compact — show filter rules, no re-enrich/cost */
            <>
              {enabled && (
                <>
                  <p className="text-[0.65rem] text-text-dim mb-2">
                    Zero-cost &middot; auto-runs after dependencies
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {stage.fields.map((f) => (
                      <span
                        key={f}
                        className="px-1.5 py-0.5 text-[0.6rem] rounded bg-surface-alt text-text-muted border border-border"
                      >
                        {f}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </>
          ) : (
            /* Normal stage: full config UI */
            <>
              {/* Stats line */}
              {enabled && estimate && (
                <p className="text-xs text-text-muted mb-2">
                  <span className="font-medium text-text">{estimate.eligible_count}</span> eligible
                  <span className="mx-1">&middot;</span>
                  {fmtCost(estimate.cost_per_item)}/item
                </p>
              )}

              {/* Re-enrich toggle */}
              {enabled && (
                <div className="mb-2">
                  <label className="flex items-center gap-1.5 text-xs text-text-muted cursor-pointer">
                    <input
                      type="checkbox"
                      checked={reEnrich.enabled}
                      onChange={(e) => onReEnrichToggle(e.target.checked)}
                      className="rounded border-border-solid text-accent focus:ring-accent/30 w-3.5 h-3.5"
                    />
                    Re-enrich outdated
                  </label>

                  {reEnrich.enabled && (
                    <div className="flex flex-wrap gap-1 mt-1.5 ml-5">
                      {HORIZON_PRESETS.map((p) => {
                        const iso = horizonToDate(p.days)
                        const isActive = reEnrich.horizon === iso
                        return (
                          <button
                            key={p.label}
                            onClick={() => onFreshnessChange(isActive ? null : iso)}
                            className={`px-2 py-0.5 text-[0.65rem] rounded border transition-colors ${
                              isActive
                                ? 'border-accent bg-accent/10 text-accent'
                                : 'border-border text-text-muted hover:border-accent/40'
                            }`}
                          >
                            {p.label}
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Field tags */}
              {enabled && (
                <div className="flex flex-wrap gap-1 mb-2">
                  {stage.fields.map((f) => (
                    <span
                      key={f}
                      className="px-1.5 py-0.5 text-[0.6rem] rounded bg-surface-alt text-text-muted border border-border"
                    >
                      {f}
                    </span>
                  ))}
                </div>
              )}

              {/* Soft dep badges */}
              {enabled && softDeps.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {softDeps.map((dep) => (
                    <button
                      key={dep.code}
                      onClick={() => onSoftDepToggle(dep.code, !dep.active)}
                      className={`flex items-center gap-1 px-2 py-0.5 text-[0.6rem] rounded-full border transition-colors ${
                        dep.active
                          ? 'border-accent/30 bg-accent/5 text-accent'
                          : 'border-border text-text-dim line-through'
                      }`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${dep.active ? 'bg-accent' : 'bg-border-solid'}`} />
                      {dep.name}
                    </button>
                  ))}
                </div>
              )}

              {/* Country gate indicator */}
              {stage.countryGate && enabled && (
                <p className="text-[0.6rem] text-text-dim mt-1.5 italic">
                  Limited to: {stage.countryGate.tlds.join(', ')}
                </p>
              )}
            </>
          )}
        </>
      )}

      {/* Running mode content */}
      {(isRunning || isCompleted) && progress && (
        <>
          {isGate ? (
            /* Gate: pass/fail counts instead of progress bar */
            <div className="mt-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-success font-medium">
                  &#10003; {progress.done - progress.failed} passed
                </span>
                {progress.failed > 0 && (
                  <span className="text-error font-medium">
                    &#10007; {progress.failed} filtered
                  </span>
                )}
              </div>
              {progress.status === 'running' && (
                <div className="mt-1.5">
                  <div className="w-full h-1 bg-surface-alt rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-accent-cyan transition-all duration-500"
                      style={{ width: `${pctDone}%` }}
                    />
                  </div>
                  <p className="text-[0.6rem] text-text-dim mt-0.5">
                    {progress.done}/{progress.total}
                  </p>
                </div>
              )}

              {/* Failed items for gate */}
              {progress.failed > 0 && progress.failed_items && progress.failed_items.length > 0 && (
                <div className="mt-1.5">
                  <button
                    onClick={() => setShowFailed(!showFailed)}
                    className="flex items-center gap-1 text-[0.6rem] text-error hover:text-error/80 transition-colors"
                  >
                    <span className={`transition-transform ${showFailed ? 'rotate-90' : ''}`}>&#9654;</span>
                    view filtered
                  </button>
                  {showFailed && (
                    <ul className="mt-1 space-y-0.5 max-h-24 overflow-y-auto">
                      {progress.failed_items.map((item, i) => (
                        <li key={i} className="text-[0.6rem] text-text-muted pl-2">
                          <span className="text-error mr-1">&#8226;</span>
                          {item.name}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          ) : (
            /* Normal stage: progress bar + cost */
            <>
              <div className="mt-2 mb-1.5">
                <div className="w-full h-1.5 bg-surface-alt rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      progress.status === 'failed' ? 'bg-error' : 'bg-accent-cyan'
                    }`}
                    style={{ width: `${pctDone}%` }}
                  />
                </div>
              </div>

              <div className="flex items-center justify-between text-xs text-text-muted">
                <span>
                  {progress.done}/{progress.total}
                  {progress.failed > 0 && (
                    <span className="text-error ml-1">({progress.failed} failed)</span>
                  )}
                </span>
                <span>{fmtCost(progress.cost)}</span>
              </div>

              {progress.current_item && progress.status === 'running' && (
                <p className="text-[0.6rem] text-text-dim mt-1 truncate">
                  {progress.current_item.name}
                </p>
              )}

              {/* Failed items expandable list */}
              {progress.failed > 0 && progress.failed_items && progress.failed_items.length > 0 && (
                <div className="mt-2 border-t border-border pt-1.5">
                  <button
                    onClick={() => setShowFailed(!showFailed)}
                    className="flex items-center gap-1 text-[0.65rem] text-error hover:text-error/80 transition-colors w-full"
                  >
                    <span className={`transition-transform ${showFailed ? 'rotate-90' : ''}`}>&#9654;</span>
                    {progress.failed_items.length} failed entit{progress.failed_items.length === 1 ? 'y' : 'ies'}
                  </button>
                  {showFailed && (
                    <ul className="mt-1 space-y-0.5 max-h-32 overflow-y-auto">
                      {progress.failed_items.map((item, i) => (
                        <li key={i} className="text-[0.6rem] text-text-muted pl-3">
                          <span className="text-error mr-1">&#8226;</span>
                          <span className="font-medium">{item.name}</span>
                          {item.error && (
                            <span className="text-text-dim ml-1" title={item.error}>
                              &mdash; {item.error.length > 40 ? item.error.slice(0, 40) + '...' : item.error}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
