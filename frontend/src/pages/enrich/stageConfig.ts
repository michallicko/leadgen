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
  countryGate?: { countries: string[]; tlds: string[] }
}

export const ROW_LABELS = [
  'Profiling',
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
    description: 'Basic company profiling: industry, size, revenue',
    fields: ['Industry', 'Business Model', 'Revenue', 'Employees', 'Summary', 'Triage Score'],
    row: 0,
    available: true,
  },
  // Row 1 — Company Intelligence
  {
    code: 'l2',
    displayName: 'Deep Research',
    entityType: 'company',
    hardDeps: ['l1'],
    softDeps: [],
    costDefault: 0.08,
    icon: 'DR',
    color: 'var(--color-accent)',
    bg: 'var(--color-accent-bg, rgba(109,99,255,0.08))',
    description: 'In-depth company intel, tech stack, pain hypothesis',
    fields: ['Company Intel', 'News', 'AI Opportunities', 'Tech Stack', 'Pain Hypothesis'],
    row: 1,
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
    description: 'Funding, M&A activity, hiring patterns',
    fields: ['Funding', 'M&A Activity', 'Hiring Patterns', 'Growth Indicators'],
    row: 1,
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
    description: 'Official company records, insolvency checks',
    fields: ['Official Name', 'Legal Form', 'Registration Status', 'Credibility Score', 'Insolvency'],
    row: 1,
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
    description: 'Media mentions, press releases, sentiment',
    fields: ['Media Mentions', 'Press Releases', 'Sentiment', 'Thought Leadership'],
    row: 1,
    available: true,
  },
  // Row 2 — Contact Intelligence
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
    description: 'Current title, reporting structure, tenure',
    fields: ['Current Title', 'Reporting Structure', 'Tenure', 'Employment Status'],
    row: 2,
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
    description: 'LinkedIn, Twitter/X, speaking engagements',
    fields: ['LinkedIn Profile', 'Twitter/X', 'Speaking Engagements', 'Publications'],
    row: 2,
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
    description: 'Previous roles, career trajectory, industry xp',
    fields: ['Previous Roles', 'Career Trajectory', 'Industry Experience'],
    row: 2,
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
    description: 'Email verification, phone, alt contacts',
    fields: ['Email Status', 'Phone', 'Alternative Contacts'],
    row: 2,
    available: true,
  },
  // Row 3 — Validation
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
    description: 'Data completeness and quality validation',
    fields: ['Quality Flags', 'Data Completeness'],
    row: 3,
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
