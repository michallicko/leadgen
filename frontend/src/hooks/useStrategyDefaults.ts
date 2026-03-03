/**
 * useStrategyDefaults -- extract common form defaults from the strategy document.
 *
 * Reads the tenant's StrategyDocument.extracted_data and derives defaults for:
 * - Campaign creation: name suggestion, primary channel, target audience
 * - Message generation: tone, style, formality
 * - Enrichment config: tier criteria from ICP
 *
 * All values are optional -- the hook returns what is available.
 * Users can always override any auto-filled value.
 *
 * BL-178: Smart Defaults -- Auto-Fill from Strategy Context
 */

import { useMemo } from 'react'
import { usePlaybookDocument } from '../api/queries/usePlaybook'

export interface StrategyDefaults {
  // Campaign creation defaults
  campaignNameSuggestion: string | null
  primaryChannel: string | null
  targetAudience: string | null

  // Message generation defaults
  tone: string | null
  formality: string | null
  language: string | null

  // ICP / enrichment defaults
  icpIndustries: string[]
  icpSeniority: string[]
  icpCompanySize: string | null
  icpRegion: string | null

  // Metadata
  hasStrategy: boolean
  isLoading: boolean
}

function extractStringField(
  data: Record<string, unknown>,
  ...paths: string[]
): string | null {
  for (const path of paths) {
    const parts = path.split('.')
    let current: unknown = data
    for (const part of parts) {
      if (current && typeof current === 'object' && part in (current as Record<string, unknown>)) {
        current = (current as Record<string, unknown>)[part]
      } else {
        current = undefined
        break
      }
    }
    if (typeof current === 'string' && current.trim()) {
      return current.trim()
    }
  }
  return null
}

function extractStringArray(
  data: Record<string, unknown>,
  path: string,
): string[] {
  const parts = path.split('.')
  let current: unknown = data
  for (const part of parts) {
    if (current && typeof current === 'object' && part in (current as Record<string, unknown>)) {
      current = (current as Record<string, unknown>)[part]
    } else {
      return []
    }
  }
  if (Array.isArray(current)) {
    return current.filter((v): v is string => typeof v === 'string' && v.trim().length > 0)
  }
  return []
}

export function useStrategyDefaults(): StrategyDefaults {
  const { data: doc, isLoading } = usePlaybookDocument()

  return useMemo(() => {
    const empty: StrategyDefaults = {
      campaignNameSuggestion: null,
      primaryChannel: null,
      targetAudience: null,
      tone: null,
      formality: null,
      language: null,
      icpIndustries: [],
      icpSeniority: [],
      icpCompanySize: null,
      icpRegion: null,
      hasStrategy: false,
      isLoading,
    }

    if (!doc || !doc.extracted_data || typeof doc.extracted_data !== 'object') {
      return { ...empty, isLoading }
    }

    const extracted = doc.extracted_data as Record<string, unknown>
    const hasStrategy = doc.status !== 'draft' || !!doc.content

    // Campaign defaults
    const objective = extractStringField(extracted, 'objective', 'campaign_goal')
    const primaryChannel = extractStringField(extracted, 'channels.primary', 'channel')
    const targetAudience = extractStringField(
      extracted,
      'icp.summary',
      'icp.description',
      'target_audience',
    )

    // Messaging defaults
    const tone = extractStringField(extracted, 'messaging.tone', 'tone')
    const formality = extractStringField(extracted, 'messaging.formality', 'formality')
    const language = extractStringField(extracted, 'messaging.language', 'language')

    // ICP defaults
    const icpIndustries = extractStringArray(extracted, 'icp.industries')
    const icpSeniority = extractStringArray(extracted, 'icp.seniority_levels')
    const icpCompanySize = extractStringField(extracted, 'icp.company_size', 'icp.headcount_range')
    const icpRegion = extractStringField(extracted, 'icp.region', 'icp.geography')

    // Generate campaign name suggestion from objective
    let campaignNameSuggestion: string | null = null
    if (objective) {
      const dateStr = new Date().toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
      const shortObj = objective.length > 40 ? objective.slice(0, 40).trim() + '...' : objective
      campaignNameSuggestion = `${shortObj} - ${dateStr}`
    }

    return {
      campaignNameSuggestion,
      primaryChannel,
      targetAudience,
      tone,
      formality,
      language,
      icpIndustries,
      icpSeniority,
      icpCompanySize,
      icpRegion,
      hasStrategy,
      isLoading,
    }
  }, [doc, isLoading])
}
