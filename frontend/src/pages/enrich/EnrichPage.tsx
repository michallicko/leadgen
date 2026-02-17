/**
 * EnrichPage — DAG-based enrichment pipeline configuration and execution.
 * Replaces the vanilla dashboard/enrich.html with a React implementation.
 */

import { useState, useRef, useCallback, useMemo } from 'react'
import { FilterBar } from '../../components/ui/FilterBar'
import { useEnrichState } from './useEnrichState'
import { useEnrichEstimate } from './useEnrichEstimate'
import { useEnrichPipeline } from './useEnrichPipeline'
import { useStageHealth } from './useStageHealth'
import { STAGE_MAP } from './stageConfig'
import { DagVisualization } from './DagVisualization'
import { DagEdges } from './DagEdges'
import { DagControls } from './DagControls'
import { CompletionPanel } from './CompletionPanel'
import { StageCard } from './StageCard'
import { CorrectiveActionModal } from './CorrectiveActionModal'
import { RunHistoryPanel } from './RunHistoryPanel'
import { RunResultsModal } from './RunResultsModal'
import type { PipelineRun } from './useRunHistory'

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

  const stageHealth = useStageHealth(filters.batch)

  // Corrective action modal state
  const [correctiveModal, setCorrectiveModal] = useState<{
    stageCode: string
    stageName: string
  } | null>(null)

  // Run results modal state
  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null)

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

  const noBatch = !filters.batch

  return (
    <div className="p-6">
      {/* Filters — always visible, disabled during pipeline run */}
      <div className={dagMode === 'running' ? 'opacity-60 pointer-events-none' : ''}>
        <FilterBar
          filters={filterConfigs}
          values={filterValues}
          onChange={handleFilterChange}
        />
      </div>

      {/* No batch selected prompt */}
      {noBatch && dagMode === 'configure' && (
        <div className="mt-12 text-center">
          <p className="text-sm text-text-muted">Select a batch to configure the enrichment pipeline.</p>
        </div>
      )}

      {/* Main content — only when batch selected */}
      {!noBatch && (
        <>
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

                // Build soft dep info (only for operational soft deps)
                const softDeps = stageDef.softDeps
                  .filter((depCode) => STAGE_MAP[depCode]?.operational)
                  .map((depCode) => ({
                    code: depCode,
                    name: STAGE_MAP[depCode]?.displayName ?? depCode,
                    active: softDepsConfig[`${stageCode}:${depCode}`] !== false,
                  }))

                const health = stageHealth.data?.stages?.[stageCode]

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
                      failedCount={health?.failed ?? 0}
                      reviewCount={health?.needs_review ?? 0}
                      onHealthClick={() => setCorrectiveModal({
                        stageCode,
                        stageName: stageDef.displayName,
                      })}
                    />
                  </div>
                )
              }}
            </DagVisualization>
          </div>

          {/* Run history panel (configure mode only) */}
          {dagMode === 'configure' && (
            <RunHistoryPanel
              batchName={filters.batch}
              onSelectRun={setSelectedRun}
            />
          )}

          {/* Completion panel */}
          {dagMode === 'completed' && (
            <CompletionPanel
              stageProgress={stageProgress}
              totalCost={totalCost}
              onReset={reset}
            />
          )}
        </>
      )}

      {/* Corrective action modal */}
      {correctiveModal && (
        <CorrectiveActionModal
          isOpen={true}
          onClose={() => setCorrectiveModal(null)}
          batchName={filters.batch}
          stageCode={correctiveModal.stageCode}
          stageName={correctiveModal.stageName}
        />
      )}

      {/* Run results modal */}
      {selectedRun && (
        <RunResultsModal
          isOpen={true}
          onClose={() => setSelectedRun(null)}
          run={selectedRun}
        />
      )}
    </div>
  )
}
