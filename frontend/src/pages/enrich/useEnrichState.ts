/**
 * Central state hook for the enrich page.
 * Manages filters, DAG mode, stage toggles, soft dep config, and re-enrich settings.
 */

import { useState, useMemo, useCallback } from 'react'
import { useLocalStorage } from '../../hooks/useLocalStorage'
import { useBatches } from '../../api/queries/useBatches'
import { filterOptions, TIER_DISPLAY } from '../../lib/display'
import { STAGES } from './stageConfig'
import type { FilterConfig } from '../../components/ui/FilterBar'
import type { DagMode, EnrichFilters, ReEnrichConfig } from './StageCard.types'

/** Default: only operational, non-terminal stages enabled */
function defaultEnabledStages(): Record<string, boolean> {
  const m: Record<string, boolean> = {}
  for (const s of STAGES) {
    m[s.code] = s.operational && !s.isTerminal
  }
  return m
}

export function useEnrichState() {
  // Filter state (persisted)
  const [batch, setBatch] = useLocalStorage('en_filter_batch', '')
  const [owner, setOwner] = useLocalStorage('en_filter_owner', '')
  const [tier, setTier] = useLocalStorage('en_filter_tier', '')
  const [entityIds, setEntityIds] = useLocalStorage('en_filter_ids', '')
  const [limit, setLimit] = useLocalStorage('en_filter_limit', '')

  // DAG mode
  const [dagMode, setDagMode] = useState<DagMode>('configure')

  // Stage toggles
  const [enabledStages, setEnabledStages] = useLocalStorage<Record<string, boolean>>(
    'en_enabled_stages',
    defaultEnabledStages(),
  )

  // Soft dep config per stage
  const [softDepsConfig, setSoftDepsConfig] = useLocalStorage<Record<string, boolean>>(
    'en_soft_deps',
    {},
  )

  // Re-enrich config per stage
  const [reEnrichConfig, setReEnrichConfig] = useState<Record<string, ReEnrichConfig>>({})

  // Pipeline run ID
  const [pipelineRunId, setPipelineRunId] = useState<string | null>(null)

  // Batches data for filter options
  const { data: batchesData } = useBatches()

  // Read entity_ids from URL params on mount
  useState(() => {
    const params = new URLSearchParams(window.location.search)
    const ids = params.get('entity_ids')
    if (ids) {
      setEntityIds(ids)
      // Clear URL param without reload
      const url = new URL(window.location.href)
      url.searchParams.delete('entity_ids')
      window.history.replaceState({}, '', url.toString())
    }
  })

  // Filter change handler
  const handleFilterChange = useCallback(
    (key: string, value: string) => {
      const setters: Record<string, (v: string) => void> = {
        batch: setBatch,
        owner: setOwner,
        tier: setTier,
        entityIds: setEntityIds,
        limit: setLimit,
      }
      setters[key]?.(value)
    },
    [setBatch, setOwner, setTier, setEntityIds, setLimit],
  )

  // Filter values object
  const filters: EnrichFilters = useMemo(
    () => ({ batch, owner, tier, entityIds, limit }),
    [batch, owner, tier, entityIds, limit],
  )

  // FilterConfig array
  const filterConfigs: FilterConfig[] = useMemo(
    () => [
      {
        key: 'batch',
        label: 'Batch',
        type: 'select' as const,
        options: (batchesData?.batches ?? []).map((b) => ({ value: b.name, label: b.name })),
      },
      {
        key: 'owner',
        label: 'Owner',
        type: 'select' as const,
        options: (batchesData?.owners ?? []).map((o) => ({ value: o.name, label: o.name })),
      },
      {
        key: 'tier',
        label: 'Tier',
        type: 'select' as const,
        options: filterOptions(TIER_DISPLAY),
      },
      {
        key: 'entityIds',
        label: 'Entity IDs',
        type: 'search' as const,
        placeholder: 'Paste entity IDs (comma-separated)...',
      },
      {
        key: 'limit',
        label: 'Limit',
        type: 'number' as const,
        placeholder: 'Limit',
        min: 1,
        max: 10000,
      },
    ],
    [batchesData],
  )

  // Stage toggle handler
  const toggleStage = useCallback(
    (code: string, enabled: boolean) => {
      setEnabledStages({ ...enabledStages, [code]: enabled })
    },
    [enabledStages, setEnabledStages],
  )

  // Soft dep toggle handler
  const toggleSoftDep = useCallback(
    (stageCode: string, depCode: string, active: boolean) => {
      setSoftDepsConfig({
        ...softDepsConfig,
        [`${stageCode}:${depCode}`]: active,
      })
    },
    [softDepsConfig, setSoftDepsConfig],
  )

  // Re-enrich toggle handler
  const toggleReEnrich = useCallback(
    (stageCode: string, enabled: boolean) => {
      setReEnrichConfig((prev) => ({
        ...prev,
        [stageCode]: { enabled, horizon: prev[stageCode]?.horizon ?? null },
      }))
    },
    [],
  )

  // Freshness horizon handler
  const setFreshness = useCallback(
    (stageCode: string, horizon: string | null) => {
      setReEnrichConfig((prev) => ({
        ...prev,
        [stageCode]: { enabled: prev[stageCode]?.enabled ?? false, horizon },
      }))
    },
    [],
  )

  // Enabled stage codes (for API calls) — only operational stages
  const enabledStageCodes = useMemo(
    () => Object.entries(enabledStages)
      .filter(([code, v]) => {
        const stage = STAGES.find(s => s.code === code)
        return v && stage?.operational
      })
      .map(([k]) => k),
    [enabledStages],
  )

  // Build soft_deps payload for API
  const softDepsPayload = useMemo(() => {
    const result: Record<string, boolean> = {}
    for (const stage of STAGES) {
      if (stage.softDeps.length > 0 && enabledStages[stage.code]) {
        const allEnabled = stage.softDeps.every(
          (dep) => softDepsConfig[`${stage.code}:${dep}`] !== false,
        )
        result[stage.code] = allEnabled
      }
    }
    return result
  }, [enabledStages, softDepsConfig])

  // Build re_enrich payload for API
  const reEnrichPayload = useMemo(() => {
    const result: Record<string, { enabled: boolean; horizon: string | null }> = {}
    for (const [code, config] of Object.entries(reEnrichConfig)) {
      if (config.enabled) {
        result[code] = config
      }
    }
    return Object.keys(result).length > 0 ? result : undefined
  }, [reEnrichConfig])

  return {
    // Filters
    filters,
    filterConfigs,
    handleFilterChange,

    // DAG mode
    dagMode,
    setDagMode,

    // Stage config
    enabledStages,
    toggleStage,
    enabledStageCodes,

    // Soft deps
    softDepsConfig,
    toggleSoftDep,
    softDepsPayload,

    // Re-enrich
    reEnrichConfig,
    toggleReEnrich,
    setFreshness,
    reEnrichPayload,

    // Pipeline
    pipelineRunId,
    setPipelineRunId,
  }
}
