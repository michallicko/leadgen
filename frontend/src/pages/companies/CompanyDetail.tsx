import { useState, useCallback } from 'react'
import { useUpdateCompany, type CompanyDetail as CompanyDetailType } from '../../api/queries/useCompanies'
import { useToast } from '../../components/ui/Toast'
import { Badge } from '../../components/ui/Badge'
import {
  FieldGrid, Field,
  EditableSelect, EditableTextarea,
  SectionDivider, MiniTable,
} from '../../components/ui/DetailField'
import { Tabs, type TabDef } from '../../components/ui/Tabs'
import { EnrichmentTimeline } from '../../components/ui/EnrichmentTimeline'
import { CorrectiveActionButtons } from '../../components/ui/CorrectiveActionButtons'
import { RichText } from '../../components/ui/RichText'
import type { SourceInfo } from '../../components/ui/SourceTooltip'
import {
  STATUS_DISPLAY, STATUS_REVERSE,
  TIER_DISPLAY, TIER_REVERSE,
  BUYING_STAGE_DISPLAY, BUYING_STAGE_REVERSE,
  ENGAGEMENT_STATUS_DISPLAY, ENGAGEMENT_STATUS_REVERSE,
  CRM_STATUS_DISPLAY, CRM_STATUS_REVERSE,
  COHORT_DISPLAY, COHORT_REVERSE,
  filterOptions,
} from '../../lib/display'

interface Props {
  company: CompanyDetailType
  onNavigate: (type: 'company' | 'contact', id: string) => void
}

export function CompanyDetail({ company, onNavigate }: Props) {
  const { toast } = useToast()
  const mutation = useUpdateCompany()

  const [edits, setEdits] = useState<Record<string, string>>({})
  const [cfEdits, setCfEdits] = useState<Record<string, string>>({})

  const handleFieldChange = useCallback((name: string, value: string) => {
    setEdits((prev) => ({ ...prev, [name]: value }))
  }, [])

  const handleCfChange = useCallback((name: string, value: string) => {
    setCfEdits((prev) => ({ ...prev, [name]: value }))
  }, [])

  const getEditableValue = (field: string, original: string | null | undefined) => {
    return field in edits ? edits[field] : (original ?? '')
  }

  const hasChanges = Object.keys(edits).length > 0 || Object.keys(cfEdits).length > 0

  const handleSave = async () => {
    const reverseMap: Record<string, Record<string, string>> = {
      status: STATUS_REVERSE,
      tier: TIER_REVERSE,
      buying_stage: BUYING_STAGE_REVERSE,
      engagement_status: ENGAGEMENT_STATUS_REVERSE,
      crm_status: CRM_STATUS_REVERSE,
      cohort: COHORT_REVERSE,
    }

    const payload: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(edits)) {
      const rev = reverseMap[key]
      payload[key] = rev ? (rev[value] ?? value) : value
    }
    if (Object.keys(cfEdits).length > 0) {
      payload.custom_fields = cfEdits
    }

    try {
      await mutation.mutateAsync({ id: company.id, data: payload })
      toast('Company updated', 'success')
      setEdits({})
      setCfEdits({})
    } catch {
      toast('Failed to save changes', 'error')
    }
  }

  const l2 = company.enrichment_l2 as Record<string, string | null> | null
  const reg = company.registry_data as Record<string, unknown> | null

  const l1Source: SourceInfo = {
    label: 'L1 Enrichment',
    timestamp: company.updated_at,
    cost: company.enrichment_cost_usd,
  }
  const l2Source: SourceInfo | undefined = l2 ? {
    label: 'L2 Enrichment',
    timestamp: (l2.enriched_at as string | null) ?? null,
    cost: (l2.enrichment_cost_usd as number | null) ?? null,
  } : undefined
  const regSource: SourceInfo | undefined = reg ? {
    label: 'Registry Lookup',
    timestamp: (reg.enriched_at as string | null) ?? null,
  } : undefined

  const needsAttention = company.status && ['Needs Review', 'Enrichment Failed', 'Enrichment L2 Failed'].includes(company.status)

  /* ---- Tab definitions ---- */

  const tabs: TabDef[] = []

  // Overview tab
  tabs.push({
    id: 'overview',
    label: 'Overview',
    content: (
      <div className="space-y-1">
        <SectionDivider title="Classification" />
        <FieldGrid cols={3}>
          <Field label="Business Model" value={company.business_model} source={l1Source} />
          <Field label="Company Size" value={company.company_size} source={l1Source} />
          <Field label="Ownership" value={company.ownership_type} source={l1Source} />
          <Field label="Geo Region" value={company.geo_region} source={l1Source} />
          <Field label="Industry" value={company.industry} source={l1Source} />
          <Field label="Industry Category" value={company.industry_category} source={l1Source} />
          <Field label="Revenue Range" value={company.revenue_range} source={l1Source} />
          <Field label="Business Type" value={company.business_type} source={l1Source} />
        </FieldGrid>

        <SectionDivider title="Pipeline" />
        <FieldGrid cols={3}>
          <EditableSelect label="Status" name="status" value={getEditableValue('status', company.status)} options={filterOptions(STATUS_DISPLAY)} onChange={handleFieldChange} />
          <EditableSelect label="Tier" name="tier" value={getEditableValue('tier', company.tier)} options={filterOptions(TIER_DISPLAY)} onChange={handleFieldChange} />
          <EditableSelect label="Buying Stage" name="buying_stage" value={getEditableValue('buying_stage', company.buying_stage)} options={filterOptions(BUYING_STAGE_DISPLAY)} onChange={handleFieldChange} />
          <EditableSelect label="Engagement" name="engagement_status" value={getEditableValue('engagement_status', company.engagement_status)} options={filterOptions(ENGAGEMENT_STATUS_DISPLAY)} onChange={handleFieldChange} />
          <EditableSelect label="CRM Status" name="crm_status" value={getEditableValue('crm_status', company.crm_status)} options={filterOptions(CRM_STATUS_DISPLAY)} onChange={handleFieldChange} />
          <EditableSelect label="Cohort" name="cohort" value={getEditableValue('cohort', company.cohort)} options={filterOptions(COHORT_DISPLAY)} onChange={handleFieldChange} />
        </FieldGrid>

        <SectionDivider title="Scores" />
        <FieldGrid cols={3}>
          <Field label="Triage Score" value={company.triage_score?.toFixed(2)} source={l1Source} />
          <Field label="Pre Score" value={company.pre_score?.toFixed(2)} source={l1Source} />
          <Field label="Verified Revenue (EUR M)" value={company.verified_revenue_eur_m} source={l1Source} />
          <Field label="Verified Employees" value={company.verified_employees} source={l1Source} />
          <Field label="Enrichment Cost (USD)" value={company.enrichment_cost_usd?.toFixed(4)} source={l1Source} />
          <Field label="AI Adoption" value={company.ai_adoption} source={l1Source} />
          <Field label="News Confidence" value={company.news_confidence} source={l1Source} />
        </FieldGrid>

        <SectionDivider title="Location" />
        <FieldGrid>
          <Field label="City" value={company.hq_city} source={l1Source} />
          <Field label="Country" value={company.hq_country} source={l1Source} />
        </FieldGrid>

        <SectionDivider title="Summary & Notes" />
        <div className="space-y-3">
          <Field label="Summary" value={company.summary} className="col-span-full" source={l1Source} />
          <EditableTextarea label="Notes" name="notes" value={getEditableValue('notes', company.notes)} onChange={handleFieldChange} />
          <EditableTextarea label="Triage Notes" name="triage_notes" value={getEditableValue('triage_notes', company.triage_notes)} onChange={handleFieldChange} />
        </div>

        {company.tags.length > 0 && (
          <>
            <SectionDivider title="Tags" />
            {Object.entries(
              company.tags.reduce<Record<string, string[]>>((acc, t) => {
                ;(acc[t.category] ??= []).push(t.value)
                return acc
              }, {}),
            ).map(([cat, values]) => (
              <div key={cat} className="mb-2">
                <span className="text-xs text-text-muted">{cat}:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {values.map((v) => (
                    <span key={v} className="px-2 py-0.5 text-xs bg-accent/10 text-accent-hover rounded border border-accent/20">
                      {v}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </>
        )}

        {company.custom_fields && Object.keys(company.custom_fields).length > 0 && (
          <>
            <SectionDivider title="Custom Fields" />
            <div className="space-y-3">
              {Object.entries(company.custom_fields).map(([key, val]) => (
                <EditableTextarea
                  key={key}
                  label={key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  name={key}
                  value={key in cfEdits ? cfEdits[key] : (val ?? '')}
                  onChange={handleCfChange}
                  rows={2}
                />
              ))}
            </div>
          </>
        )}

        {hasChanges && (
          <div className="sticky bottom-0 bg-surface border-t border-border-solid py-3 mt-4 flex justify-end">
            <button
              onClick={handleSave}
              disabled={mutation.isPending}
              className="px-4 py-2 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-md transition-colors disabled:opacity-50"
            >
              {mutation.isPending ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        )}
      </div>
    ),
  })

  // Intelligence tab (only if L2 or registry data exists)
  // Helper: safely extract string from L2 data (handles arrays like quick_wins)
  const l2Text = (key: string): string | null => {
    if (!l2) return null
    const raw = l2[key]
    if (raw == null || raw === '') return null
    if (typeof raw === 'string') return raw === '-' ? null : raw
    if (Array.isArray(raw)) {
      // quick_wins is [{use_case, impact, evidence, complexity}, …]
      return raw
        .map((item, i) => {
          if (typeof item === 'string') return `${i + 1}. ${item}`
          if (typeof item === 'object' && item !== null) {
            const obj = item as Record<string, unknown>
            const title = obj.use_case || obj.title || obj.name || ''
            const desc = obj.impact || obj.description || obj.detail || ''
            const extra = obj.complexity ? ` (${obj.complexity})` : ''
            if (!title && !desc) return `${i + 1}. ${JSON.stringify(obj)}`
            return `${i + 1}. **${title}**${extra} — ${desc}`
          }
          return `${i + 1}. ${String(item)}`
        })
        .join('\n')
    }
    return String(raw)
  }

  /** Render a prose section — heading + rich text. Skips if content is empty. */
  const ProseSection = ({ title, content }: { title: string; content: string | null }) => {
    if (!content) return null
    return (
      <div>
        <h3 className="text-sm font-semibold text-text mb-2">{title}</h3>
        <RichText text={content} />
      </div>
    )
  }

  /** Check if any of the given L2 keys have content */
  const hasAnyL2 = (...keys: string[]) => keys.some((k) => l2Text(k) != null)

  if (l2 || reg) {
    tabs.push({
      id: 'intelligence',
      label: 'Intelligence',
      content: (
        <div className="max-w-3xl space-y-8">
          {l2 && (
            <>
              {/* ---- Company Profile ---- */}
              {hasAnyL2('key_products', 'customer_segments', 'competitors') && (
                <section className="space-y-5">
                  <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">Company Profile</h2>
                  <ProseSection title="Key Products & Services" content={l2Text('key_products')} />
                  <ProseSection title="Customer Segments" content={l2Text('customer_segments')} />
                  <ProseSection title="Competitors" content={l2Text('competitors')} />
                </section>
              )}

              {/* ---- Leadership & People ---- */}
              {hasAnyL2('leadership_team', 'leadership_changes', 'hiring_signals', 'ai_hiring') && (
                <section className="space-y-5 border-t border-border/40 pt-8">
                  <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">Leadership & People</h2>
                  <ProseSection title="Leadership Team" content={l2Text('leadership_team')} />
                  <ProseSection title="Leadership Changes" content={l2Text('leadership_changes')} />
                  <ProseSection title="Hiring Signals" content={l2Text('hiring_signals')} />
                  <ProseSection title="AI Hiring Activity" content={l2Text('ai_hiring')} />
                </section>
              )}

              {/* ---- Technology & Digital ---- */}
              {hasAnyL2('digital_initiatives', 'tech_stack', 'tech_partnerships', 'certifications') && (
                <section className="space-y-5 border-t border-border/40 pt-8">
                  <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">Technology & Digital</h2>
                  <ProseSection title="Digital Initiatives" content={l2Text('digital_initiatives')} />
                  <ProseSection title="Tech Stack" content={l2Text('tech_stack')} />
                  <ProseSection title="Technology Partnerships" content={l2Text('tech_partnerships')} />
                  <ProseSection title="Certifications" content={l2Text('certifications')} />
                </section>
              )}

              {/* ---- Market Intelligence ---- */}
              {hasAnyL2('recent_news', 'funding_history', 'eu_grants', 'competitor_ai_moves') && (
                <section className="space-y-5 border-t border-border/40 pt-8">
                  <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">Market Intelligence</h2>
                  <ProseSection title="Recent News" content={l2Text('recent_news')} />
                  <ProseSection title="Funding History" content={l2Text('funding_history')} />
                  <ProseSection title="EU Grants" content={l2Text('eu_grants')} />
                  <ProseSection title="Competitor AI Moves" content={l2Text('competitor_ai_moves')} />
                </section>
              )}

              {/* ---- AI Opportunity Assessment ---- */}
              {hasAnyL2('ai_opportunities', 'pain_hypothesis', 'industry_pain_points', 'cross_functional_pain', 'quick_wins', 'adoption_barriers', 'relevant_case_study') && (
                <section className="space-y-5 border-t border-border/40 pt-8">
                  <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">AI Opportunity Assessment</h2>
                  <ProseSection title="AI Opportunities" content={l2Text('ai_opportunities')} />
                  <ProseSection title="Pain Hypothesis" content={l2Text('pain_hypothesis')} />
                  <ProseSection title="Industry Pain Points" content={l2Text('industry_pain_points')} />
                  <ProseSection title="Cross-Functional Pain" content={l2Text('cross_functional_pain')} />
                  <ProseSection title="Quick Wins" content={l2Text('quick_wins')} />
                  <ProseSection title="Adoption Barriers" content={l2Text('adoption_barriers')} />
                  <ProseSection title="Relevant Case Study" content={l2Text('relevant_case_study')} />
                </section>
              )}

              {/* ---- Enrichment Quality (metadata) ---- */}
              {l2Text('company_intel') && (
                <section className="space-y-3 border-t border-border/40 pt-8">
                  <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">Enrichment Quality</h2>
                  <div className="bg-surface-alt/50 rounded-lg border border-border/30 p-4">
                    <RichText text={l2Text('company_intel')!} className="text-text-muted" />
                  </div>
                  {l2Source && (
                    <p className="text-xs text-text-dim">
                      Enriched {l2Source.timestamp ? new Date(l2Source.timestamp).toLocaleDateString() : '—'}
                      {l2Source.cost != null && ` · $${Number(l2Source.cost).toFixed(4)}`}
                    </p>
                  )}
                </section>
              )}
            </>
          )}

          {/* ---- Legal & Registry ---- */}
          {reg && (
            <section className="space-y-4 border-t border-border/40 pt-8">
              <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">Legal & Registry</h2>
              {reg.credibility_score != null && (
                <div className="mb-1">
                  <span className="text-xs text-text-muted">Credibility Score:</span>
                  <span className="ml-2 text-sm font-medium text-accent-cyan">{String(reg.credibility_score)}%</span>
                </div>
              )}
              <FieldGrid cols={3}>
                <Field label="Official Name" value={reg.official_name as string} source={regSource} />
                <Field label="ICO" value={reg.ico as string} source={regSource} />
                <Field label="DIC" value={reg.dic as string} source={regSource} />
                <Field label="Legal Form" value={reg.legal_form_name as string} source={regSource} />
                <Field label="Established" value={reg.date_established as string} source={regSource} />
                <Field label="Dissolved" value={reg.date_dissolved as string} source={regSource} />
                <Field label="City" value={reg.address_city as string} source={regSource} />
                <Field label="Postal Code" value={reg.address_postal_code as string} source={regSource} />
                <Field label="Registration Court" value={reg.registration_court as string} source={regSource} />
                <Field label="Registration Number" value={reg.registration_number as string} source={regSource} />
                <Field label="Registered Capital" value={reg.registered_capital as string} source={regSource} />
                <Field label="Status" value={reg.registration_status as string} source={regSource} />
                <Field label="Country" value={reg.registration_country as string} source={regSource} />
                <Field label="Match Confidence" value={reg.match_confidence as number} source={regSource} />
                <Field label="Match Method" value={reg.match_method as string} source={regSource} />
                <Field label="Insolvency" value={reg.insolvency_flag ? 'Yes' : 'No'} source={regSource} />
              </FieldGrid>
              <Field label="Address" value={reg.registered_address as string} className="mt-3" source={regSource} />

              {Array.isArray(reg.directors) && reg.directors.length > 0 && (
                <>
                  <h4 className="text-xs text-text-muted font-medium mt-4 mb-2">Directors</h4>
                  <div className="text-sm text-text space-y-1">
                    {(reg.directors as Array<Record<string, string>>).map((d, i) => (
                      <div key={i}>{String(d.name || d.jmeno || JSON.stringify(d))}</div>
                    ))}
                  </div>
                </>
              )}
              {Array.isArray(reg.nace_codes) && reg.nace_codes.length > 0 && (
                <>
                  <h4 className="text-xs text-text-muted font-medium mt-4 mb-2">NACE Codes</h4>
                  <div className="flex flex-wrap gap-1">
                    {(reg.nace_codes as Array<Record<string, string>>).map((n, i) => (
                      <span key={i} className="px-2 py-0.5 text-xs bg-surface-alt rounded border border-border-solid text-text-muted">
                        {String(n.code || n.kod)}: {String(n.name || n.nazev || '')}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </section>
          )}
        </div>
      ),
    })
  }

  // Contacts tab (only if contacts exist)
  if (company.contacts.length > 0) {
    tabs.push({
      id: 'contacts',
      label: 'Contacts',
      count: company.contacts.length,
      content: (
        <MiniTable
          columns={[
            { key: 'full_name', label: 'Name' },
            { key: 'job_title', label: 'Title' },
            { key: 'email_address', label: 'Email' },
            { key: 'icp_fit', label: 'ICP', render: (c) => <Badge variant="icp" value={c.icp_fit as string} /> },
            { key: 'contact_score', label: 'Score' },
          ]}
          data={company.contacts as unknown as Array<Record<string, unknown>>}
          onRowClick={(c) => onNavigate('contact', c.id as string)}
        />
      ),
    })
  }

  // History tab — timeline + timestamps + errors merged
  tabs.push({
    id: 'history',
    label: 'History',
    content: (
      <div className="space-y-1">
        <SectionDivider title="Enrichment Timeline" />
        <EnrichmentTimeline entries={[
          { label: 'Created', timestamp: company.created_at },
          ...(company.stage_completions ?? []).map((sc) => ({
            label: sc.stage.toUpperCase(),
            timestamp: sc.completed_at,
            cost: sc.cost_usd,
            status: sc.status as 'completed' | 'failed' | 'skipped',
            error: sc.error,
          })),
        ]} />

        <SectionDivider title="Timestamps" />
        <FieldGrid>
          <Field label="Created" value={company.created_at ? new Date(company.created_at).toLocaleString() : null} />
          <Field label="Updated" value={company.updated_at ? new Date(company.updated_at).toLocaleString() : null} />
        </FieldGrid>

        {company.error_message && (
          <>
            <SectionDivider title="Errors" />
            <div className="bg-error/10 border border-error/30 rounded-md p-3 text-sm text-error">
              {company.error_message}
            </div>
          </>
        )}
      </div>
    ),
  })

  return (
    <div>
      {/* Header — badges + metadata */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <Badge variant="status" value={company.status} />
        <Badge variant="tier" value={company.tier} />
        {company.owner_name && <span className="text-xs text-text-muted">{company.owner_name}</span>}
        {company.batch_name && <span className="text-xs text-text-dim">{company.batch_name}</span>}
      </div>

      {/* Corrective actions for failed/review entities */}
      {needsAttention && (
        <div className="mb-4 p-3 bg-surface-alt rounded-lg border border-border-solid">
          <p className="text-xs text-text-muted mb-2">This company requires attention:</p>
          <CorrectiveActionButtons companyId={company.id} />
        </div>
      )}

      {/* Tabbed content */}
      <Tabs tabs={tabs} />
    </div>
  )
}
