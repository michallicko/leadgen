import { useState, useCallback, useMemo } from 'react'

export interface MultiFilterValue {
  values: string[]
  exclude: boolean
}

export interface AdvancedFilterState {
  search: string
  tag_name: string
  owner_name: string
  icp_fit: string
  message_status: string
  // Multi-select filters
  industry: MultiFilterValue
  company_size: MultiFilterValue
  geo_region: MultiFilterValue
  revenue_range: MultiFilterValue
  seniority_level: MultiFilterValue
  department: MultiFilterValue
  job_titles: MultiFilterValue
  linkedin_activity: MultiFilterValue
}

const EMPTY_MULTI: MultiFilterValue = { values: [], exclude: false }

const DEFAULT_STATE: AdvancedFilterState = {
  search: '',
  tag_name: '',
  owner_name: '',
  icp_fit: '',
  message_status: '',
  industry: { ...EMPTY_MULTI },
  company_size: { ...EMPTY_MULTI },
  geo_region: { ...EMPTY_MULTI },
  revenue_range: { ...EMPTY_MULTI },
  seniority_level: { ...EMPTY_MULTI },
  department: { ...EMPTY_MULTI },
  job_titles: { ...EMPTY_MULTI },
  linkedin_activity: { ...EMPTY_MULTI },
}

const MULTI_KEYS = [
  'industry', 'company_size', 'geo_region', 'revenue_range',
  'seniority_level', 'department', 'job_titles', 'linkedin_activity',
] as const

type MultiKey = typeof MULTI_KEYS[number]

function loadState(storageKey: string): AdvancedFilterState {
  try {
    const saved = localStorage.getItem(storageKey)
    if (saved) {
      const parsed = JSON.parse(saved)
      return { ...DEFAULT_STATE, ...parsed }
    }
  } catch { /* ignore */ }
  return { ...DEFAULT_STATE }
}

function saveState(storageKey: string, state: AdvancedFilterState) {
  try {
    localStorage.setItem(storageKey, JSON.stringify(state))
  } catch { /* ignore */ }
}

export function useAdvancedFilters(storageKey: string) {
  const [filters, setFilters] = useState<AdvancedFilterState>(() => loadState(storageKey))

  const setSimpleFilter = useCallback((key: string, value: string) => {
    setFilters(prev => {
      const next = { ...prev, [key]: value }
      saveState(storageKey, next)
      return next
    })
  }, [storageKey])

  const setMultiFilter = useCallback((key: MultiKey, values: string[], exclude?: boolean) => {
    setFilters(prev => {
      const current = prev[key] as MultiFilterValue
      const next = {
        ...prev,
        [key]: { values, exclude: exclude !== undefined ? exclude : current.exclude },
      }
      saveState(storageKey, next)
      return next
    })
  }, [storageKey])

  const toggleExclude = useCallback((key: MultiKey) => {
    setFilters(prev => {
      const current = prev[key] as MultiFilterValue
      const next = {
        ...prev,
        [key]: { ...current, exclude: !current.exclude },
      }
      saveState(storageKey, next)
      return next
    })
  }, [storageKey])

  const clearFilter = useCallback((key: string) => {
    setFilters(prev => {
      const isMulti = MULTI_KEYS.includes(key as MultiKey)
      const next = {
        ...prev,
        [key]: isMulti ? { ...EMPTY_MULTI } : '',
      }
      saveState(storageKey, next)
      return next
    })
  }, [storageKey])

  const clearAll = useCallback(() => {
    const next = { ...DEFAULT_STATE }
    saveState(storageKey, next)
    setFilters(next)
  }, [storageKey])

  const activeFilterCount = useMemo(() => {
    let count = 0
    for (const key of MULTI_KEYS) {
      if (filters[key].values.length > 0) count++
    }
    return count
  }, [filters])

  const toQueryParams = useCallback((): Record<string, string> => {
    const params: Record<string, string> = {}
    // Simple filters
    if (filters.search) params.search = filters.search
    if (filters.tag_name) params.tag_name = filters.tag_name
    if (filters.owner_name) params.owner_name = filters.owner_name
    if (filters.icp_fit) params.icp_fit = filters.icp_fit
    if (filters.message_status) params.message_status = filters.message_status
    // Multi-value filters
    for (const key of MULTI_KEYS) {
      const f = filters[key]
      if (f.values.length > 0) {
        params[key] = f.values.join(',')
        if (f.exclude) params[`${key}_exclude`] = 'true'
      }
    }
    return params
  }, [filters])

  const toCountsPayload = useCallback(() => {
    const filtersPayload: Record<string, { values: string[]; exclude: boolean }> = {}
    for (const key of MULTI_KEYS) {
      const f = filters[key]
      if (f.values.length > 0) {
        filtersPayload[key] = { values: f.values, exclude: f.exclude }
      }
    }
    return {
      filters: filtersPayload,
      search: filters.search || undefined,
      tag_name: filters.tag_name || undefined,
      owner_name: filters.owner_name || undefined,
    }
  }, [filters])

  return {
    filters,
    setSimpleFilter,
    setMultiFilter,
    toggleExclude,
    clearFilter,
    clearAll,
    activeFilterCount,
    toQueryParams,
    toCountsPayload,
  }
}
