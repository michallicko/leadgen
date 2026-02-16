import { useState, useCallback } from 'react'
import { useUpdateContact, type ContactDetail as ContactDetailType } from '../../api/queries/useContacts'
import { useToast } from '../../components/ui/Toast'
import { Badge } from '../../components/ui/Badge'
import {
  FieldGrid, Field, FieldLink,
  EditableSelect, EditableTextarea,
  SectionDivider, MiniTable,
  CollapsibleSection,
} from '../../components/ui/DetailField'
import { EnrichmentTimeline } from '../../components/ui/EnrichmentTimeline'
import type { SourceInfo } from '../../components/ui/SourceTooltip'
import {
  SENIORITY_DISPLAY, SENIORITY_REVERSE,
  DEPARTMENT_DISPLAY, DEPARTMENT_REVERSE,
  ICP_FIT_DISPLAY, ICP_FIT_REVERSE,
  RELATIONSHIP_STATUS_DISPLAY, RELATIONSHIP_STATUS_REVERSE,
  CONTACT_SOURCE_DISPLAY, CONTACT_SOURCE_REVERSE,
  LANGUAGE_DISPLAY, LANGUAGE_REVERSE,
  MESSAGE_STATUS_REVERSE,
  filterOptions,
} from '../../lib/display'

interface Props {
  contact: ContactDetailType
  onNavigate: (type: 'company' | 'contact', id: string) => void
}

export function ContactDetail({ contact, onNavigate }: Props) {
  const { toast } = useToast()
  const mutation = useUpdateContact()

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
      seniority_level: SENIORITY_REVERSE,
      department: DEPARTMENT_REVERSE,
      icp_fit: ICP_FIT_REVERSE,
      relationship_status: RELATIONSHIP_STATUS_REVERSE,
      contact_source: CONTACT_SOURCE_REVERSE,
      language: LANGUAGE_REVERSE,
      message_status: MESSAGE_STATUS_REVERSE,
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
      await mutation.mutateAsync({ id: contact.id, data: payload })
      toast('Contact updated', 'success')
      setEdits({})
      setCfEdits({})
    } catch {
      toast('Failed to save changes', 'error')
    }
  }

  // Source info helpers
  const personSource: SourceInfo | undefined = contact.enrichment ? {
    label: 'Person Enrichment',
    timestamp: contact.enrichment.enriched_at,
    cost: contact.enrichment.enrichment_cost_usd,
  } : undefined

  return (
    <div className="space-y-1">
      {/* Header */}
      <div className="flex items-start gap-4 mb-4">
        {contact.profile_photo_url && (
          <img
            src={contact.profile_photo_url}
            alt={contact.full_name}
            className="w-14 h-14 rounded-full object-cover border border-border-solid"
          />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="icp" value={contact.icp_fit} />
            <Badge variant="msgStatus" value={contact.message_status} />
            {contact.owner_name && <span className="text-xs text-text-muted">{contact.owner_name}</span>}
            {contact.batch_name && <span className="text-xs text-text-dim">{contact.batch_name}</span>}
          </div>
          {contact.linkedin_url && (
            <a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-xs text-accent-cyan hover:underline mt-1 inline-block">
              LinkedIn Profile
            </a>
          )}
        </div>
      </div>

      {/* Company link */}
      {contact.company && (
        <>
          <SectionDivider title="Company" />
          <button
            onClick={() => contact.company && onNavigate('company', contact.company.id)}
            className="w-full text-left flex items-center gap-3 px-3 py-2 rounded-md bg-surface-alt border border-border-solid hover:border-accent/40 transition-colors"
          >
            <div className="flex-1 min-w-0">
              <span className="text-sm font-medium text-text">{contact.company.name}</span>
              {contact.company.domain && (
                <span className="text-xs text-text-dim ml-2">{contact.company.domain}</span>
              )}
            </div>
            <Badge variant="status" value={contact.company.status} />
            <Badge variant="tier" value={contact.company.tier} />
          </button>
        </>
      )}

      {/* Contact Info */}
      <SectionDivider title="Contact Info" />
      <FieldGrid>
        <FieldLink label="Email" value={contact.email_address} href={contact.email_address ? `mailto:${contact.email_address}` : null} />
        <Field label="Phone" value={contact.phone_number} />
        <Field label="City" value={contact.location_city} />
        <Field label="Country" value={contact.location_country} />
      </FieldGrid>

      {/* Classification (editable) */}
      <SectionDivider title="Classification" />
      <FieldGrid>
        <EditableSelect
          label="Seniority"
          name="seniority_level"
          value={getEditableValue('seniority_level', contact.seniority_level)}
          options={filterOptions(SENIORITY_DISPLAY)}
          onChange={handleFieldChange}
        />
        <EditableSelect
          label="Department"
          name="department"
          value={getEditableValue('department', contact.department)}
          options={filterOptions(DEPARTMENT_DISPLAY)}
          onChange={handleFieldChange}
        />
        <EditableSelect
          label="ICP Fit"
          name="icp_fit"
          value={getEditableValue('icp_fit', contact.icp_fit)}
          options={filterOptions(ICP_FIT_DISPLAY)}
          onChange={handleFieldChange}
        />
        <EditableSelect
          label="Relationship"
          name="relationship_status"
          value={getEditableValue('relationship_status', contact.relationship_status)}
          options={filterOptions(RELATIONSHIP_STATUS_DISPLAY)}
          onChange={handleFieldChange}
        />
        <EditableSelect
          label="Source"
          name="contact_source"
          value={getEditableValue('contact_source', contact.contact_source)}
          options={filterOptions(CONTACT_SOURCE_DISPLAY)}
          onChange={handleFieldChange}
        />
        <EditableSelect
          label="Language"
          name="language"
          value={getEditableValue('language', contact.language)}
          options={filterOptions(LANGUAGE_DISPLAY)}
          onChange={handleFieldChange}
        />
      </FieldGrid>

      {/* Scores */}
      <SectionDivider title="Scores" />
      <FieldGrid>
        <Field label="Contact Score" value={contact.contact_score} />
        <Field label="AI Champion" value={contact.ai_champion} />
        <Field label="AI Champion Score" value={contact.ai_champion_score} />
        <Field label="Authority Score" value={contact.authority_score} />
        <Field label="Enrichment Cost (USD)" value={contact.enrichment_cost_usd?.toFixed(4)} />
      </FieldGrid>

      {/* Person Enrichment */}
      {contact.enrichment && (
        <CollapsibleSection title="Person Enrichment" defaultOpen>
          <div className="space-y-3">
            <Field label="Person Summary" value={contact.enrichment.person_summary} className="col-span-full" source={personSource} />
            <Field label="LinkedIn Summary" value={contact.enrichment.linkedin_profile_summary} className="col-span-full" source={personSource} />
            <Field label="Relationship Synthesis" value={contact.enrichment.relationship_synthesis} className="col-span-full" source={personSource} />
            <FieldGrid>
              <Field label="Enriched At" value={contact.enrichment.enriched_at ? new Date(contact.enrichment.enriched_at).toLocaleString() : null} />
              <Field label="Cost (USD)" value={contact.enrichment.enrichment_cost_usd?.toFixed(4)} />
            </FieldGrid>
          </div>
        </CollapsibleSection>
      )}

      {/* Notes (editable) */}
      <SectionDivider title="Notes" />
      <EditableTextarea
        label="Notes"
        name="notes"
        value={getEditableValue('notes', contact.notes)}
        onChange={handleFieldChange}
      />

      {/* Custom Fields */}
      {contact.custom_fields && Object.keys(contact.custom_fields).length > 0 && (
        <>
          <SectionDivider title="Custom Fields" />
          <div className="space-y-3">
            {Object.entries(contact.custom_fields).map(([key, val]) => (
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

      {/* Messages mini-table */}
      {contact.messages.length > 0 && (
        <>
          <SectionDivider title={`Messages (${contact.messages.length})`} />
          <MiniTable
            columns={[
              { key: 'channel', label: 'Channel' },
              { key: 'sequence_step', label: 'Step' },
              { key: 'variant', label: 'Variant' },
              { key: 'subject', label: 'Subject' },
              { key: 'status', label: 'Status', render: (m) => <Badge variant="msgStatus" value={m.status as string} /> },
              { key: 'tone', label: 'Tone' },
            ]}
            data={contact.messages as unknown as Array<Record<string, unknown>>}
            emptyText="No messages"
          />
        </>
      )}

      {/* Status Flags */}
      <SectionDivider title="Status Flags" />
      <FieldGrid>
        <Field label="Processed (Enrich)" value={contact.processed_enrich} />
        <Field label="Email Lookup" value={contact.email_lookup} />
        <Field label="Duplicity Check" value={contact.duplicity_check} />
        <Field label="Duplicity Conflict" value={contact.duplicity_conflict} />
        <Field label="Duplicity Detail" value={contact.duplicity_detail} />
      </FieldGrid>
      {contact.error && (
        <div className="bg-error/10 border border-error/30 rounded-md p-3 text-sm text-error mt-2">
          {contact.error}
        </div>
      )}

      {/* Enrichment Timeline */}
      <CollapsibleSection title="Enrichment Timeline">
        <EnrichmentTimeline entries={[
          { label: 'Created', timestamp: contact.created_at },
          ...(contact.enrichment?.enriched_at ? [{
            label: 'Person Enrichment',
            timestamp: contact.enrichment.enriched_at,
            cost: contact.enrichment.enrichment_cost_usd,
          }] : []),
        ]} />
      </CollapsibleSection>

      {/* Timestamps */}
      <SectionDivider title="Timestamps" />
      <FieldGrid>
        <Field label="Created" value={contact.created_at ? new Date(contact.created_at).toLocaleString() : null} />
        <Field label="Updated" value={contact.updated_at ? new Date(contact.updated_at).toLocaleString() : null} />
      </FieldGrid>
    </div>
  )
}
