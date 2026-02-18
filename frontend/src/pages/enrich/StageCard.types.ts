/** Types for the StageCard component and pipeline state. */

export interface StageEstimate {
  eligible_count: number
  cost_per_item: number
  estimated_cost: number
  fields: string[]
}

export interface FailedItem {
  name: string
  error?: string
}

export interface StageProgress {
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
  total: number
  done: number
  failed: number
  cost: number
  current_item?: { name: string; status: string }
  failed_items?: FailedItem[]
}

export interface ReEnrichConfig {
  enabled: boolean
  horizon: string | null
}

export type DagMode = 'configure' | 'running' | 'completed'

export interface EnrichFilters {
  search: string
  tag: string
  owner: string
  tier: string
  status: string
  entityIds: string
  limit: string
}
