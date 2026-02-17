/**
 * EnrichPage — DAG-based enrichment pipeline configuration and execution.
 * Replaces the vanilla dashboard/enrich.html with a React implementation.
 */

import { useRef, useCallback, useMemo } from 'react'
import { FilterBar } from '../../components/ui/FilterBar'
import { useEnrichState } from './useEnrichState'
import { useEnrichEstimate } from './useEnrichEstimate'
import { useEnrichPipeline } from './useEnrichPipeline'
import { STAGE_MAP } from './stageConfig'
import { DagVisualization } from './DagVisualization'
import { DagEdges } from './DagEdges'
import { DagControls } from './DagControls'
import { CompletionPanel } from './CompletionPanel'
import { StageCard } from './StageCard'

export function EnrichPage() {
  const state = useEnrichState()
  const {
    filters,
    filterConfigs,
    handleFilterChange,
    enabledStages,
    toggleStage,
    enabledStageCodes,
    softDepsConfig,
    toggleSoftDep,
    softDepsPayload,
    reEnrichConfig,
    toggleReEnrich,
    setFreshness,
    reEnrichPayload,
  } = state

  const pipeline = useEnrichPipeline(filters)
  const { dagMode, stageProgress, totalCost, start, stop, reset } = pipeline

  const estimate = useEnrichEstimate(
    filters,
    enabledStageCodes,
    softDepsPayload,
    reEnrichPayload,
  )

  // Card refs for edge drawing
  const containerRef = useRef<HTMLDivElement>(null)
  const cardRefsObj = useRef<Record<string, HTMLDivElement | null>>({})
  const setCardRef = useCallback((code: string) => (el: HTMLDivElement | null) => {
    cardRefsObj.current[code] = el
  }, [])

  // Run handler
  const handleRun = useCallback(() => {
    start({
      batch_name: filters.batch,
      owner: filters.owner || undefined,
      tier_filter: filters.tier ? [filters.tier] : undefined,
      stages: enabledStageCodes,
      soft_deps: softDepsPayload,
      sample_size: filters.limit ? Number(filters.limit) : undefined,
      entity_ids: filters.entityIds
        ? filters.entityIds.split(',').map((s) => s.trim()).filter(Boolean)
        : undefined,
      re_enrich: reEnrichPayload,
    })
  }, [start, filters, enabledStageCodes, softDepsPayload, reEnrichPayload])

  const estimatedCost = estimate.data?.total_estimated_cost ?? 0

  // Convert typed filters to Record<string, string> for FilterBar
  const filterValues: Record<string, string> = useMemo(
    () => ({ ...filters }),
    [filters],
  )

  return (
    <div className="p-6">
      {/* Filters */}
      <FilterBar
        filters={filterConfigs}
        values={filterValues}
        onChange={handleFilterChange}
      />

      {/* Controls bar */}
      <DagControls
        mode={dagMode}
        batchName={filters.batch}
        estimatedCost={estimatedCost}
        runningCost={totalCost}
        enabledCount={enabledStageCodes.length}
        onRun={handleRun}
        onStop={stop}
        isLoading={estimate.isLoading}
      />

      {/* DAG with edges */}
      <div className="relative" ref={containerRef}>
        <DagEdges
          containerRef={containerRef}
          cardRefs={cardRefsObj.current}
          enabledStages={enabledStages}
          mode={dagMode}
          progress={stageProgress}
          softDepsConfig={softDepsConfig}
        />
        <DagVisualization>
          {(stageCode) => {
            const stageDef = STAGE_MAP[stageCode]
            if (!stageDef) return null

            // Build soft dep info
            const softDeps = stageDef.softDeps.map((depCode) => ({
              code: depCode,
              name: STAGE_MAP[depCode]?.displayName ?? depCode,
              active: softDepsConfig[`${stageCode}:${depCode}`] !== false,
            }))

            return (
              <div key={stageCode} ref={setCardRef(stageCode)}>
                <StageCard
                  stage={stageDef}
                  mode={dagMode}
                  estimate={estimate.data?.stages?.[stageCode] ?? null}
                  enabled={enabledStages[stageCode] ?? false}
                  onToggle={(v) => toggleStage(stageCode, v)}
                  progress={stageProgress[stageCode] ?? null}
                  softDeps={softDeps}
                  onSoftDepToggle={(dep, active) => toggleSoftDep(stageCode, dep, active)}
                  reEnrich={reEnrichConfig[stageCode] ?? { enabled: false, horizon: null }}
                  onReEnrichToggle={(v) => toggleReEnrich(stageCode, v)}
                  onFreshnessChange={(h) => setFreshness(stageCode, h)}
                />
              </div>
            )
          }}
        </DagVisualization>
      </div>

      {/* Completion panel */}
      {dagMode === 'completed' && (
        <CompletionPanel
          stageProgress={stageProgress}
          totalCost={totalCost}
          onReset={reset}
        />
      )}
    </div>
  )
}
