/**
 * Derive a human-readable pipeline stage from entity_stage_completions.
 * Mirrors the _derive_stage() logic in api/routes/company_routes.py.
 */

export interface StageCompletion {
  stage: string
  status: string
  cost_usd?: number | null
  completed_at?: string | null
}

export interface DerivedStage {
  label: string
  stage: string | null
  color: string
}

const STAGE_ORDER = [
  'l1',
  'triage',
  'signals',
  'registry',
  'news',
  'l2',
  'person',
  'social',
  'career',
  'contact_details',
  'generate',
  'review',
  'qc',
] as const

const STAGE_CONFIG: Record<string, { label: string; color: string }> = {
  l1: { label: 'Classified', color: '#6366f1' },              // indigo
  triage: { label: 'Qualified', color: '#8b5cf6' },            // violet
  signals: { label: 'Strategic Signals', color: '#a855f7' },   // purple
  registry: { label: 'Legal & Registry', color: '#7c3aed' },   // violet-dark
  news: { label: 'News & PR', color: '#2563eb' },              // blue
  l2: { label: 'Researched', color: '#06b6d4' },               // cyan
  person: { label: 'Contacts Ready', color: '#14b8a6' },       // teal
  social: { label: 'Social & Online', color: '#0d9488' },      // teal-dark
  career: { label: 'Career History', color: '#059669' },        // emerald
  contact_details: { label: 'Contact Details', color: '#10b981' }, // green-light
  generate: { label: 'Messages Generated', color: '#f59e0b' }, // amber
  review: { label: 'Ready for Outreach', color: '#22c55e' },   // green
  qc: { label: 'Quality Checked', color: '#16a34a' },          // green-dark
}

/**
 * Compute derived stage from completions array.
 * Falls back to the legacy status field if no completions exist.
 */
export function deriveStage(
  completions: StageCompletion[] | null | undefined,
  _status?: string | null,
): DerivedStage {
  if (!completions || completions.length === 0) {
    return { label: 'New', stage: null, color: '#94a3b8' } // slate
  }

  const completed = new Set(
    completions.filter((c) => c.status === 'completed').map((c) => c.stage),
  )

  // Walk stage order in reverse to find the latest completed
  for (let i = STAGE_ORDER.length - 1; i >= 0; i--) {
    const stage = STAGE_ORDER[i]
    if (completed.has(stage)) {
      const config = STAGE_CONFIG[stage]
      return { label: config.label, stage, color: config.color }
    }
  }

  return { label: 'New', stage: null, color: '#94a3b8' }
}
