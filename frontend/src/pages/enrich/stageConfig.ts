/**
 * Client-side stage registry — mirrors api/services/stage_registry.py.
 * Defines DAG structure, display metadata, and field outputs for each stage.
 */

export interface StageDef {
  code: string
  displayName: string
  entityType: 'company' | 'contact'
  hardDeps: string[]
  softDeps: string[]
  costDefault: number
  icon: string
  color: string
  bg: string
  description: string
  fields: string[]
  row: number
  available: boolean
  isTerminal?: boolean
  isGate?: boolean
  countryGate?: { countries: string[]; tlds: string[] }
}

export const ROW_LABELS = [
  'Profiling',
  'Qualification',
  'Company Intelligence',
  'Contact Intelligence',
  'Validation',
]

const STAGE_DEFS: StageDef[] = [
  // Row 0 — Profiling
  {
    code: 'l1',
    displayName: 'Company Profile',
    entityType: 'company',
    hardDeps: [],
    softDeps: [],
    costDefault: 0.02,
    icon: 'CP',
    color: 'var(--color-accent-cyan)',
    bg: 'var(--color-accent-cyan-bg, rgba(0,184,207,0.08))',
    description: 'AI-powered company profiling via web research. Extracts industry, business model, size, revenue, and generates a triage score for qualification. Essential first step for all downstream enrichment.',
    fields: ['Industry', 'Business Model', 'Revenue', 'Employees', 'Summary', 'Triage Score'],
    row: 0,
    available: true,
  },
  {
    code: 'triage',
    displayName: 'Triage',
    entityType: 'company',
    hardDeps: ['l1'],
    softDeps: [],
    costDefault: 0.00,
    icon: 'TG',
    color: '#06d6a0',
    bg: 'rgba(6,214,160,0.08)',
    description: 'Zero-cost qualification gate. Filters companies by tier, industry, geography, revenue, and B2B fit. Only companies that pass proceed to deeper (more expensive) enrichment stages.',
    fields: ['Tier Filter', 'Industry Filter', 'B2B Check', 'Revenue Floor'],
    row: 1,
    available: true,
    isGate: true,
  },
  // Row 2 — Company Intelligence
  {
    code: 'l2',
    displayName: 'Deep Research',
    entityType: 'company',
    hardDeps: ['triage'],
    softDeps: [],
    costDefault: 0.08,
    icon: 'DR',
    color: 'var(--color-accent)',
    bg: 'var(--color-accent-bg, rgba(109,99,255,0.08))',
    description: 'Deep-dive company intelligence: tech stack analysis, AI adoption opportunities, competitive landscape, and pain hypothesis generation. Powers hyper-personalized outreach angles.',
    fields: ['Company Intel', 'News', 'AI Opportunities', 'Tech Stack', 'Pain Hypothesis'],
    row: 2,
    available: true,
  },
  {
    code: 'signals',
    displayName: 'Strategic Signals',
    entityType: 'company',
    hardDeps: ['l1'],
    softDeps: [],
    costDefault: 0.05,
    icon: 'SS',
    color: '#e09f3e',
    bg: 'rgba(224,159,62,0.08)',
    description: 'Strategic buying signals: recent funding rounds, M&A activity, executive hires, expansion indicators. Identifies companies with active budgets and change momentum.',
    fields: ['Funding', 'M&A Activity', 'Hiring Patterns', 'Growth Indicators'],
    row: 2,
    available: true,
  },
  {
    code: 'registry',
    displayName: 'Legal & Registry',
    entityType: 'company',
    hardDeps: ['l1'],
    softDeps: [],
    costDefault: 0.00,
    icon: 'LR',
    color: '#7b8794',
    bg: 'rgba(123,135,148,0.08)',
    description: 'Official business registry data: legal status, registration details, insolvency checks. Adds credibility scoring and filters out shell companies or dissolved entities.',
    fields: ['Official Name', 'Legal Form', 'Registration Status', 'Credibility Score', 'Insolvency'],
    row: 2,
    available: true,
    countryGate: {
      countries: ['CZ', 'Czech Republic', 'Czechia', 'NO', 'Norway', 'Norge', 'FI', 'Finland', 'Suomi', 'FR', 'France'],
      tlds: ['.cz', '.no', '.fi', '.fr'],
    },
  },
  {
    code: 'news',
    displayName: 'News & PR',
    entityType: 'company',
    hardDeps: ['l1'],
    softDeps: [],
    costDefault: 0.04,
    icon: 'NP',
    color: '#48bfe3',
    bg: 'rgba(72,191,227,0.08)',
    description: 'Recent media coverage, press releases, and industry mentions. Surfaces timely conversation starters and reveals company positioning and thought leadership topics.',
    fields: ['Media Mentions', 'Press Releases', 'Sentiment', 'Thought Leadership'],
    row: 2,
    available: true,
  },
  // Row 3 — Contact Intelligence
  {
    code: 'person',
    displayName: 'Role & Employment',
    entityType: 'contact',
    hardDeps: ['l1'],
    softDeps: ['l2', 'signals'],
    costDefault: 0.04,
    icon: 'RE',
    color: '#9b5de5',
    bg: 'rgba(155,93,229,0.08)',
    description: 'Contact-level intelligence: current role verification, seniority level, reporting structure, and tenure. Ensures you reach the right decision-maker with the right context.',
    fields: ['Current Title', 'Reporting Structure', 'Tenure', 'Employment Status'],
    row: 3,
    available: true,
  },
  {
    code: 'social',
    displayName: 'Social & Online',
    entityType: 'contact',
    hardDeps: ['l1'],
    softDeps: ['l2', 'signals'],
    costDefault: 0.03,
    icon: 'SO',
    color: '#f15bb5',
    bg: 'rgba(241,91,181,0.08)',
    description: 'Social media presence analysis: LinkedIn activity, Twitter/X engagement, speaking engagements, publications. Identifies communication style and preferred engagement channels.',
    fields: ['LinkedIn Profile', 'Twitter/X', 'Speaking Engagements', 'Publications'],
    row: 3,
    available: true,
  },
  {
    code: 'career',
    displayName: 'Career History',
    entityType: 'contact',
    hardDeps: ['l1'],
    softDeps: ['l2'],
    costDefault: 0.03,
    icon: 'CH',
    color: '#00bbf9',
    bg: 'rgba(0,187,249,0.08)',
    description: 'Career trajectory analysis: previous companies, role progression, industry transitions. Reveals shared experiences and talking points for personalized outreach.',
    fields: ['Previous Roles', 'Career Trajectory', 'Industry Experience'],
    row: 3,
    available: true,
  },
  {
    code: 'contact_details',
    displayName: 'Contact Details',
    entityType: 'contact',
    hardDeps: ['l1'],
    softDeps: [],
    costDefault: 0.01,
    icon: 'CD',
    color: '#80ed99',
    bg: 'rgba(128,237,153,0.08)',
    description: 'Contact details verification: email deliverability check, phone numbers, alternative contact channels. Ensures messages reach inboxes and reduces bounce rates.',
    fields: ['Email Status', 'Phone', 'Alternative Contacts'],
    row: 3,
    available: true,
  },
  // Row 4 — Validation
  {
    code: 'qc',
    displayName: 'Quality Check',
    entityType: 'company',
    hardDeps: [],
    softDeps: [],
    costDefault: 0.00,
    icon: 'QC',
    color: '#06d6a0',
    bg: 'rgba(6,214,160,0.08)',
    description: 'Automated data quality check: validates completeness, consistency, and accuracy across all enriched fields. Flags entities needing manual review before outreach.',
    fields: ['Quality Flags', 'Data Completeness'],
    row: 4,
    available: true,
    isTerminal: true,
  },
]

/** All stages as array */
export const STAGES = STAGE_DEFS

/** Map from stage code to definition */
export const STAGE_MAP: Record<string, StageDef> = Object.fromEntries(
  STAGE_DEFS.map((s) => [s.code, s]),
)

/** Pre-computed ancestor map: stage -> all transitive dependencies */
export const STAGE_ANCESTORS: Record<string, string[]> = (() => {
  const result: Record<string, string[]> = {}

  function getAncestors(code: string, visited = new Set<string>()): string[] {
    if (visited.has(code)) return []
    visited.add(code)
    const stage = STAGE_MAP[code]
    if (!stage) return []

    const deps = [...stage.hardDeps, ...stage.softDeps]
    const ancestors: string[] = []
    for (const dep of deps) {
      ancestors.push(dep)
      ancestors.push(...getAncestors(dep, visited))
    }
    return [...new Set(ancestors)]
  }

  for (const stage of STAGE_DEFS) {
    result[stage.code] = getAncestors(stage.code)
  }
  return result
})()

/** Get stages grouped by row */
export function getStagesByRow(): { label: string; stages: StageDef[] }[] {
  return ROW_LABELS.map((label, idx) => ({
    label,
    stages: STAGE_DEFS.filter((s) => s.row === idx),
  }))
}
