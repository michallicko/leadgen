import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { useUpdateCompany, type CompanyDetail as CompanyDetailType } from '../../api/queries/useCompanies'
import { useToast } from '../../components/ui/Toast'
import { Badge } from '../../components/ui/Badge'
import {
  FieldGrid, Field,
  EditableSelect, EditableTextarea,
  CollapsibleSection, SectionDivider, MiniTable,
} from '../../components/ui/DetailField'
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
  namespace?: string
  onClose: () => void
}

export function CompanyDetail({ company, namespace, onClose }: Props) {
  const navigate = useNavigate()
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

  const l2 = company.enrichment_l2 as Record<string, string | null> | null
  const reg = company.registry_data as Record<string, unknown> | null

  return (
    <div className="space-y-1">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <Badge variant="status" value={company.status} />
        <Badge variant="tier" value={company.tier} />
        {company.owner_name && <span className="text-xs text-text-muted">{company.owner_name}</span>}
        {company.batch_name && <span className="text-xs text-text-dim">{company.batch_name}</span>}
      </div>

      {/* Classification */}
      <SectionDivider title="Classification" />
      <FieldGrid>
        <Field label="Business Model" value={company.business_model} />
        <Field label="Company Size" value={company.company_size} />
        <Field label="Ownership" value={company.ownership_type} />
        <Field label="Geo Region" value={company.geo_region} />
        <Field label="Industry" value={company.industry} />
        <Field label="Industry Category" value={company.industry_category} />
        <Field label="Revenue Range" value={company.revenue_range} />
        <Field label="Business Type" value={company.business_type} />
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
        <Field label="Triage Score" value={company.triage_score?.toFixed(2)} />
        <Field label="Pre Score" value={company.pre_score?.toFixed(2)} />
        <Field label="Verified Revenue (EUR M)" value={company.verified_revenue_eur_m} />
        <Field label="Verified Employees" value={company.verified_employees} />
        <Field label="Enrichment Cost (USD)" value={company.enrichment_cost_usd?.toFixed(4)} />
        <Field label="AI Adoption" value={company.ai_adoption} />
        <Field label="News Confidence" value={company.news_confidence} />
      </FieldGrid>

      {/* Location */}
      <SectionDivider title="Location" />
      <FieldGrid>
        <Field label="City" value={company.hq_city} />
        <Field label="Country" value={company.hq_country} />
      </FieldGrid>

      {/* Summary & Notes (editable) */}
      <SectionDivider title="Summary & Notes" />
      <div className="space-y-3">
        <Field label="Summary" value={company.summary} className="col-span-full" />
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

      {/* L2 Enrichment (collapsible) */}
      {l2 && (
        <CollapsibleSection title="L2 Enrichment">
          <FieldGrid>
            <Field label="Company Intel" value={l2.company_intel} className="col-span-full" />
            <Field label="Recent News" value={l2.recent_news} className="col-span-full" />
            <Field label="AI Opportunities" value={l2.ai_opportunities} className="col-span-full" />
            <Field label="Pain Hypothesis" value={l2.pain_hypothesis} className="col-span-full" />
            <Field label="Relevant Case Study" value={l2.relevant_case_study} className="col-span-full" />
            <Field label="Digital Initiatives" value={l2.digital_initiatives} className="col-span-full" />
            <Field label="Leadership Changes" value={l2.leadership_changes} />
            <Field label="Hiring Signals" value={l2.hiring_signals} />
            <Field label="Key Products" value={l2.key_products} />
            <Field label="Customer Segments" value={l2.customer_segments} />
            <Field label="Competitors" value={l2.competitors} />
            <Field label="Tech Stack" value={l2.tech_stack} />
            <Field label="Funding History" value={l2.funding_history} />
            <Field label="EU Grants" value={l2.eu_grants} />
            <Field label="Leadership Team" value={l2.leadership_team} />
            <Field label="AI Hiring" value={l2.ai_hiring} />
            <Field label="Tech Partnerships" value={l2.tech_partnerships} />
            <Field label="Certifications" value={l2.certifications} />
            <Field label="Quick Wins" value={l2.quick_wins} className="col-span-full" />
            <Field label="Industry Pain Points" value={l2.industry_pain_points} className="col-span-full" />
            <Field label="Cross-Functional Pain" value={l2.cross_functional_pain} className="col-span-full" />
            <Field label="Adoption Barriers" value={l2.adoption_barriers} className="col-span-full" />
            <Field label="Competitor AI Moves" value={l2.competitor_ai_moves} className="col-span-full" />
          </FieldGrid>
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
            <Field label="Official Name" value={reg.official_name as string} />
            <Field label="ICO" value={reg.ico as string} />
            <Field label="DIC" value={reg.dic as string} />
            <Field label="Legal Form" value={reg.legal_form_name as string} />
            <Field label="Established" value={reg.date_established as string} />
            <Field label="Dissolved" value={reg.date_dissolved as string} />
            <Field label="Address" value={reg.registered_address as string} className="col-span-full" />
            <Field label="City" value={reg.address_city as string} />
            <Field label="Postal Code" value={reg.address_postal_code as string} />
            <Field label="Registration Court" value={reg.registration_court as string} />
            <Field label="Registration Number" value={reg.registration_number as string} />
            <Field label="Registered Capital" value={reg.registered_capital as string} />
            <Field label="Status" value={reg.registration_status as string} />
            <Field label="Country" value={reg.registration_country as string} />
            <Field label="Match Confidence" value={reg.match_confidence as number} />
            <Field label="Match Method" value={reg.match_method as string} />
            <Field label="Insolvency" value={reg.insolvency_flag ? 'Yes' : 'No'} />
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
            onRowClick={(c) => {
              onClose()
              navigate(`/${namespace}/contacts?open=${c.id}`)
            }}
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

      {/* Timestamps */}
      <SectionDivider title="Timestamps" />
      <FieldGrid>
        <Field label="Created" value={company.created_at ? new Date(company.created_at).toLocaleString() : null} />
        <Field label="Updated" value={company.updated_at ? new Date(company.updated_at).toLocaleString() : null} />
      </FieldGrid>
    </div>
  )
}
