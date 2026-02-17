import { useState, useCallback } from 'react'
import { useUpdateCompany, type CompanyDetail as CompanyDetailType, type CompanyEnrichmentL1 } from '../../api/queries/useCompanies'
import { useToast } from '../../components/ui/Toast'
import { Badge } from '../../components/ui/Badge'
import {
  FieldGrid, Field,
  EditableSelect, EditableTextarea,
  CollapsibleSection, SectionDivider, MiniTable,
} from '../../components/ui/DetailField'
import { EnrichmentTimeline } from '../../components/ui/EnrichmentTimeline'
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

  // Editable fields — track local changes
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
    // Build payload with reverse-mapped values
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

  const l1 = company.enrichment_l1
  const l2 = company.enrichment_l2 as Record<string, unknown> | null
  const reg = company.registry_data as Record<string, unknown> | null

  // Source info helpers
  const l1Source: SourceInfo = {
    label: 'L1 Enrichment',
    timestamp: l1?.enriched_at ?? company.updated_at,
    cost: l1?.enrichment_cost_usd ?? company.enrichment_cost_usd,
  }
  const l2Source: SourceInfo | undefined = l2 ? {
    label: 'L2 Enrichment',
    timestamp: (l2.enriched_at as string) ?? null,
    cost: (l2.enrichment_cost_usd as number) ?? null,
  } : undefined
  const regSource: SourceInfo | undefined = reg ? {
    label: 'Registry Lookup',
    timestamp: (reg.enriched_at as string | null) ?? null,
  } : undefined

  return (
    <div className="space-y-1">
      {/* Header */}
      <div className="flex items-start gap-3 mb-4">
        {company.logo_url ? (
          <img src={company.logo_url} alt="" className="w-8 h-8 rounded-md object-cover flex-shrink-0" />
        ) : (
          <div className="w-8 h-8 rounded-md bg-surface-alt border border-border-solid flex items-center justify-center text-sm font-medium text-text-muted flex-shrink-0">
            {company.name.charAt(0).toUpperCase()}
          </div>
        )}
        <div className="min-w-0 flex-1">
          {(company.domain || company.website_url || company.linkedin_url) && (
            <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted mb-1">
              {company.domain && <span>{company.domain}</span>}
              {company.website_url && (
                <a href={company.website_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:text-accent-hover">
                  Website ↗
                </a>
              )}
              {company.linkedin_url && (
                <a href={company.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:text-accent-hover">
                  LinkedIn ↗
                </a>
              )}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="status" value={company.status} />
            <Badge variant="tier" value={company.tier} />
            {company.data_quality_score != null && (
              <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                company.data_quality_score >= 80 ? 'bg-success/10 text-success' :
                company.data_quality_score >= 50 ? 'bg-warning/10 text-warning' :
                'bg-error/10 text-error'
              }`}>
                Quality: {company.data_quality_score}
              </span>
            )}
            {company.owner_name && <span className="text-xs text-text-muted">{company.owner_name}</span>}
            {company.tag_name && <span className="text-xs text-text-dim">{company.tag_name}</span>}
          </div>
        </div>
      </div>

      {/* Classification */}
      <SectionDivider title="Classification" />
      <FieldGrid>
        <Field label="Business Model" value={company.business_model} source={l1Source} />
        <Field label="Company Size" value={company.company_size} source={l1Source} />
        <Field label="Ownership" value={company.ownership_type} source={l1Source} />
        <Field label="Geo Region" value={company.geo_region} source={l1Source} />
        <Field label="Industry" value={company.industry} source={l1Source} />
        <Field label="Industry Category" value={company.industry_category} source={l1Source} />
        <Field label="Revenue Range" value={company.revenue_range} source={l1Source} />
        <Field label="Business Type" value={company.business_type} source={l1Source} />
      </FieldGrid>

      {/* Pipeline (editable) */}
      <SectionDivider title="Pipeline" />
      <FieldGrid>
        <EditableSelect
          label="Status"
          name="status"
          value={getEditableValue('status', company.status)}
          options={filterOptions(STATUS_DISPLAY)}
          onChange={handleFieldChange}
        />
        <EditableSelect
          label="Tier"
          name="tier"
          value={getEditableValue('tier', company.tier)}
          options={filterOptions(TIER_DISPLAY)}
          onChange={handleFieldChange}
        />
        <EditableSelect
          label="Buying Stage"
          name="buying_stage"
          value={getEditableValue('buying_stage', company.buying_stage)}
          options={filterOptions(BUYING_STAGE_DISPLAY)}
          onChange={handleFieldChange}
        />
        <EditableSelect
          label="Engagement"
          name="engagement_status"
          value={getEditableValue('engagement_status', company.engagement_status)}
          options={filterOptions(ENGAGEMENT_STATUS_DISPLAY)}
          onChange={handleFieldChange}
        />
        <EditableSelect
          label="CRM Status"
          name="crm_status"
          value={getEditableValue('crm_status', company.crm_status)}
          options={filterOptions(CRM_STATUS_DISPLAY)}
          onChange={handleFieldChange}
        />
        <EditableSelect
          label="Cohort"
          name="cohort"
          value={getEditableValue('cohort', company.cohort)}
          options={filterOptions(COHORT_DISPLAY)}
          onChange={handleFieldChange}
        />
      </FieldGrid>

      {/* Scores */}
      <SectionDivider title="Scores" />
      <FieldGrid>
        <Field label="Triage Score" value={company.triage_score?.toFixed(2)} source={l1Source} />
        <Field label="Pre Score" value={company.pre_score?.toFixed(2)} source={l1Source} />
        <Field label="Verified Revenue (EUR M)" value={company.verified_revenue_eur_m} source={l1Source} />
        <Field label="Verified Employees" value={company.verified_employees} source={l1Source} />
        <Field label="Enrichment Cost (USD)" value={company.enrichment_cost_usd?.toFixed(4)} source={l1Source} />
        <Field label="AI Adoption" value={company.ai_adoption} source={l1Source} />
        <Field label="News Confidence" value={company.news_confidence} source={l1Source} />
      </FieldGrid>

      {/* Location */}
      <SectionDivider title="Location" />
      <FieldGrid>
        <Field label="City" value={company.hq_city} source={l1Source} />
        <Field label="Country" value={company.hq_country} source={l1Source} />
      </FieldGrid>

      {/* Summary & Notes (editable) */}
      <SectionDivider title="Summary & Notes" />
      <div className="space-y-3">
        <Field label="Summary" value={company.summary} className="col-span-full" source={l1Source} />
        <EditableTextarea
          label="Notes"
          name="notes"
          value={getEditableValue('notes', company.notes)}
          onChange={handleFieldChange}
        />
        <EditableTextarea
          label="Triage Notes"
          name="triage_notes"
          value={getEditableValue('triage_notes', company.triage_notes)}
          onChange={handleFieldChange}
        />
      </div>

      {/* Custom Fields */}
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

      {/* Save button */}
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

      {/* L1 Enrichment (collapsible) */}
      {l1 && (
        <CollapsibleSection title="L1 Enrichment"
          badge={l1.confidence != null ? (
            <span className="text-xs text-accent-cyan">{Math.round(l1.confidence * 100)}%</span>
          ) : undefined}
        >
          <FieldGrid>
            <Field label="Confidence" value={l1.confidence != null ? `${(l1.confidence * 100).toFixed(0)}%` : null} />
            <Field label="Quality Score" value={l1.quality_score} />
            <Field label="Cost (USD)" value={l1.enrichment_cost_usd?.toFixed(4)} />
            <Field label="Enriched" value={l1.enriched_at ? new Date(l1.enriched_at).toLocaleString() : null} />
          </FieldGrid>
          {l1.qc_flags && (typeof l1.qc_flags === 'string' ? JSON.parse(l1.qc_flags) : l1.qc_flags).length > 0 && (
            <div className="mt-2">
              <span className="text-xs text-text-muted">QC Flags:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {(typeof l1.qc_flags === 'string' ? JSON.parse(l1.qc_flags) : l1.qc_flags).map((flag: string) => (
                  <span key={flag} className="px-2 py-0.5 text-xs bg-warning/10 text-warning rounded border border-warning/20">
                    {flag}
                  </span>
                ))}
              </div>
            </div>
          )}
          {l1.research_query && (
            <p className="mt-2 text-xs text-text-dim">Query: {l1.research_query}</p>
          )}
        </CollapsibleSection>
      )}

      {/* L2 Enrichment (collapsible, grouped by module) */}
      {l2 && (
        <CollapsibleSection title="L2 Enrichment">
          {/* Company Profile */}
          {(l2.company_intel || l2.key_products || l2.customer_segments || l2.competitors || l2.tech_stack || l2.leadership_team || l2.certifications) && (
            <>
              <h4 className="text-xs text-text-muted font-medium mt-2 mb-2 uppercase tracking-wider">Company Profile</h4>
              <FieldGrid>
                <Field label="Company Intel" value={l2.company_intel as string} className="col-span-full" source={l2Source} />
                <Field label="Key Products" value={l2.key_products as string} source={l2Source} />
                <Field label="Customer Segments" value={l2.customer_segments as string} source={l2Source} />
                <Field label="Competitors" value={l2.competitors as string} source={l2Source} />
                <Field label="Tech Stack" value={l2.tech_stack as string} source={l2Source} />
                <Field label="Leadership Team" value={l2.leadership_team as string} source={l2Source} />
                <Field label="Certifications" value={l2.certifications as string} source={l2Source} />
              </FieldGrid>
            </>
          )}

          {/* Strategic Signals */}
          {(l2.digital_initiatives || l2.leadership_changes || l2.hiring_signals || l2.ai_hiring || l2.tech_partnerships || l2.competitor_ai_moves || l2.ai_adoption_level || l2.news_confidence || l2.growth_indicators || l2.job_posting_count || l2.hiring_departments) && (
            <>
              <h4 className="text-xs text-text-muted font-medium mt-4 mb-2 uppercase tracking-wider">Strategic Signals</h4>
              <FieldGrid>
                <Field label="Digital Initiatives" value={l2.digital_initiatives as string} className="col-span-full" source={l2Source} />
                <Field label="Leadership Changes" value={l2.leadership_changes as string} source={l2Source} />
                <Field label="Hiring Signals" value={l2.hiring_signals as string} source={l2Source} />
                <Field label="AI Hiring" value={l2.ai_hiring as string} source={l2Source} />
                <Field label="Tech Partnerships" value={l2.tech_partnerships as string} source={l2Source} />
                <Field label="Competitor AI Moves" value={l2.competitor_ai_moves as string} className="col-span-full" source={l2Source} />
                <Field label="AI Adoption Level" value={l2.ai_adoption_level as string} source={l2Source} />
                <Field label="News Confidence" value={l2.news_confidence as string} source={l2Source} />
                <Field label="Growth Indicators" value={l2.growth_indicators as string} className="col-span-full" source={l2Source} />
                <Field label="Job Posting Count" value={l2.job_posting_count as number} source={l2Source} />
                <Field label="Hiring Departments" value={Array.isArray(l2.hiring_departments) ? (l2.hiring_departments as string[]).join(', ') : l2.hiring_departments as string} source={l2Source} />
              </FieldGrid>
            </>
          )}

          {/* Market Intel */}
          {(l2.recent_news || l2.funding_history || l2.eu_grants || l2.media_sentiment || l2.press_releases || l2.thought_leadership) && (
            <>
              <h4 className="text-xs text-text-muted font-medium mt-4 mb-2 uppercase tracking-wider">Market Intel</h4>
              <FieldGrid>
                <Field label="Recent News" value={l2.recent_news as string} className="col-span-full" source={l2Source} />
                <Field label="Funding History" value={l2.funding_history as string} source={l2Source} />
                <Field label="EU Grants" value={l2.eu_grants as string} source={l2Source} />
                <Field label="Media Sentiment" value={l2.media_sentiment as string} className="col-span-full" source={l2Source} />
                <Field label="Press Releases" value={l2.press_releases as string} className="col-span-full" source={l2Source} />
                <Field label="Thought Leadership" value={l2.thought_leadership as string} className="col-span-full" source={l2Source} />
              </FieldGrid>
            </>
          )}

          {/* Sales Opportunity */}
          {(l2.pain_hypothesis || l2.relevant_case_study || l2.ai_opportunities || l2.quick_wins || l2.industry_pain_points || l2.cross_functional_pain || l2.adoption_barriers) && (
            <>
              <h4 className="text-xs text-text-muted font-medium mt-4 mb-2 uppercase tracking-wider">Sales Opportunity</h4>
              <FieldGrid>
                <Field label="Pain Hypothesis" value={l2.pain_hypothesis as string} className="col-span-full" source={l2Source} />
                <Field label="Relevant Case Study" value={l2.relevant_case_study as string} className="col-span-full" source={l2Source} />
                <Field label="AI Opportunities" value={l2.ai_opportunities as string} className="col-span-full" source={l2Source} />
                <Field label="Quick Wins" value={Array.isArray(l2.quick_wins) ? (l2.quick_wins as Array<Record<string, unknown>>).map(w => typeof w === 'string' ? w : `${w.use_case ?? ''} (${w.complexity ?? ''}): ${w.impact ?? ''}`).join(' | ') : l2.quick_wins as string} className="col-span-full" source={l2Source} />
                <Field label="Industry Pain Points" value={l2.industry_pain_points as string} className="col-span-full" source={l2Source} />
                <Field label="Cross-Functional Pain" value={l2.cross_functional_pain as string} className="col-span-full" source={l2Source} />
                <Field label="Adoption Barriers" value={l2.adoption_barriers as string} className="col-span-full" source={l2Source} />
              </FieldGrid>
            </>
          )}
        </CollapsibleSection>
      )}

      {/* Legal & Registry (collapsible) */}
      {reg && (
        <CollapsibleSection title="Legal & Registry"
          badge={reg.credibility_score != null ? (
            <span className="text-xs text-accent-cyan">{String(reg.credibility_score)}%</span>
          ) : undefined}
        >
          <FieldGrid>
            <Field label="Official Name" value={reg.official_name as string} source={regSource} />
            <Field label="ICO" value={reg.ico as string} source={regSource} />
            <Field label="DIC" value={reg.dic as string} source={regSource} />
            <Field label="Legal Form" value={reg.legal_form_name as string} source={regSource} />
            <Field label="Established" value={reg.date_established as string} source={regSource} />
            <Field label="Dissolved" value={reg.date_dissolved as string} source={regSource} />
            <Field label="Address" value={reg.registered_address as string} className="col-span-full" source={regSource} />
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
        </CollapsibleSection>
      )}

      {/* Tags */}
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

      {/* Contacts mini-table */}
      {company.contacts.length > 0 && (
        <>
          <SectionDivider title={`Contacts (${company.contacts.length})`} />
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
        </>
      )}

      {/* Error */}
      {company.error_message && (
        <>
          <SectionDivider title="Errors" />
          <div className="bg-error/10 border border-error/30 rounded-md p-3 text-sm text-error">
            {company.error_message}
          </div>
        </>
      )}

      {/* Enrichment Timeline */}
      <CollapsibleSection title="Enrichment Timeline">
        <EnrichmentTimeline entries={[
          { label: 'Created', timestamp: company.created_at },
          ...(l1?.enriched_at || company.triage_score != null ? [{
            label: 'L1 Enrichment',
            timestamp: l1?.enriched_at ?? company.updated_at,
            cost: l1?.enrichment_cost_usd ?? company.enrichment_cost_usd,
            detail: company.triage_score != null ? `Triage score: ${company.triage_score.toFixed(2)}` : null,
          }] : []),
          ...(l2 && (l2.enriched_at as string) ? [{
            label: 'L2 Enrichment', timestamp: l2.enriched_at as string,
            cost: (l2.enrichment_cost_usd as number | null) ?? null,
          }] : []),
          ...(reg && (reg.enriched_at as string) ? [{
            label: 'Registry Lookup', timestamp: reg.enriched_at as string,
          }] : []),
        ]} />
      </CollapsibleSection>

      {/* Timestamps */}
      <SectionDivider title="Timestamps" />
      <FieldGrid>
        <Field label="Created" value={company.created_at ? new Date(company.created_at).toLocaleString() : null} />
        <Field label="Updated" value={company.updated_at ? new Date(company.updated_at).toLocaleString() : null} />
      </FieldGrid>
    </div>
  )
}
