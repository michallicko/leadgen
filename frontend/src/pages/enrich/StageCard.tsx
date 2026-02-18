/**
 * StageCard — self-contained DAG node card for a single enrichment stage.
 * Renders differently based on DagMode: configure (toggle, estimate, re-enrich)
 * vs running (progress bar, cost) vs completed (final stats).
 */

import { useState, useRef, useEffect } from 'react'
import type { StageDef } from './stageConfig'
import type { StageEstimate, StageProgress, ReEnrichConfig, DagMode } from './StageCard.types'

/** Stages that support boost mode (maps to BOOST_MODELS in stage_registry.py) */
const BOOST_STAGES = new Set(['l1', 'l2', 'person'])

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
  boost?: boolean
  onBoostToggle?: (enabled: boolean) => void
  upstreamEligible?: number
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
  boost = false,
  onBoostToggle,
  upstreamEligible,
}: StageCardProps) {
  const [showFailed, setShowFailed] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const settingsRef = useRef<HTMLDivElement>(null)
  const isRunning = mode === 'running'
  const isCompleted = mode === 'completed'

  const isGate = !!stage.isGate
  const hasSettings = !isGate && (BOOST_STAGES.has(stage.code) || true) // all non-gate stages have re-enrich

  // Close settings on outside click
  useEffect(() => {
    if (!showSettings) return
    const handleClick = (e: MouseEvent) => {
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) {
        setShowSettings(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [showSettings])

  // Card visual state
  const statusClass = (() => {
    if (!enabled && mode === 'configure') return 'opacity-50'
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

  // Settings indicators (show active settings as subtle badges)
  const settingsActive = boost || reEnrich.enabled

  return (
    <div
      className={`rounded-lg border bg-surface p-4 transition-all duration-200 flex-shrink-0 ${isGate ? 'w-[220px]' : 'w-[280px]'} ${statusClass}`}
      style={{ borderColor: enabled && mode === 'configure' ? stage.color : undefined }}
    >
      {/* Header: icon + name + settings gear + toggle/status */}
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

        <div className="flex items-center gap-1.5">
          {/* Settings gear — only in configure mode for non-gate stages */}
          {mode === 'configure' && enabled && hasSettings && !isGate && (
            <div className="relative" ref={settingsRef}>
              <button
                onClick={() => setShowSettings(!showSettings)}
                className={`p-1 rounded transition-colors ${
                  settingsActive
                    ? 'text-accent hover:text-accent/80'
                    : 'text-text-dim hover:text-text-muted'
                }`}
                title="Stage settings"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
              </button>

              {/* Settings dropdown */}
              {showSettings && (
                <div className="absolute right-0 top-7 z-20 w-56 bg-surface border border-border rounded-lg shadow-lg p-3 space-y-3">
                  {/* Re-enrich toggle */}
                  <div>
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

                  {/* Boost toggle — only for stages with boost models */}
                  {BOOST_STAGES.has(stage.code) && onBoostToggle && (
                    <div className="border-t border-border pt-2">
                      <label className="flex items-center gap-1.5 text-xs text-text-muted cursor-pointer">
                        <input
                          type="checkbox"
                          checked={boost}
                          onChange={(e) => onBoostToggle(e.target.checked)}
                          className="rounded border-border-solid text-amber-500 focus:ring-amber-500/30 w-3.5 h-3.5"
                        />
                        <span className="text-amber-500">&#9889;</span> Boost mode
                      </label>
                      <p className="text-[0.6rem] text-text-dim ml-5 mt-0.5">
                        Higher quality model &middot; ~2&times; cost
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Toggle / status */}
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
      </div>

      {/* Configure mode content */}
      {mode === 'configure' && (
        <>
          {/* Description — always visible */}
          <p className="text-xs text-text-muted leading-relaxed mb-2">
            {stage.description}
          </p>

          {isGate ? (
            /* Gate cards: compact — show filter rules */
            <>
              {/* Settings indicators */}
              {enabled && (
                <p className="text-[0.65rem] text-text-dim mb-2">
                  Zero-cost &middot; auto-runs after dependencies
                </p>
              )}
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
          ) : (
            /* Normal stage: config UI */
            <>
              {/* Stats line — show cost and eligible count */}
              {enabled && estimate && (
                <p className="text-xs text-text-muted mb-2">
                  <span className="font-medium text-text">{estimate.eligible_count}</span> eligible
                  {estimate.eligible_count === 0 && upstreamEligible && upstreamEligible > 0 && (
                    <span className="text-text-dim"> (up to {upstreamEligible})</span>
                  )}
                  <span className="mx-1">&middot;</span>
                  {fmtCost(estimate.cost_per_item)}/item
                  {boost && <span className="text-amber-500 ml-1">&#9889;</span>}
                </p>
              )}

              {/* Stats when disabled — show what it would cost */}
              {!enabled && estimate && (
                <p className="text-xs text-text-dim mb-2">
                  {fmtCost(stage.costDefault)}/item
                </p>
              )}

              {/* Active settings badges */}
              {enabled && settingsActive && (
                <div className="flex flex-wrap gap-1 mb-2">
                  {boost && (
                    <span className="px-1.5 py-0.5 text-[0.6rem] rounded bg-amber-500/10 text-amber-500 border border-amber-500/20">
                      &#9889; Boost 2&times;
                    </span>
                  )}
                  {reEnrich.enabled && (
                    <span className="px-1.5 py-0.5 text-[0.6rem] rounded bg-accent/10 text-accent border border-accent/20">
                      Re-enrich
                    </span>
                  )}
                </div>
              )}

              {/* Field tags — always visible */}
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
              {stage.countryGate && (
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
