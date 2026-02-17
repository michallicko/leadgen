import { useState, useCallback, useMemo } from 'react'
import {
  useUpdateCampaign,
  useCampaignContacts,
  useCampaignTemplates,
  useAddCampaignContacts,
  useRemoveCampaignContacts,
  type CampaignDetail as CampaignDetailType,
  type CampaignContactItem,
  type TemplateStep,
} from '../../api/queries/useCampaigns'
import { useToast } from '../../components/ui/Toast'
import {
  FieldGrid, Field,
  EditableSelect, EditableTextarea,
  SectionDivider, MiniTable,
} from '../../components/ui/DetailField'
import { ContactPicker } from './ContactPicker'

const STATUS_COLORS: Record<string, string> = {
  Draft: 'bg-[#8B92A0]/10 text-text-muted border-[#8B92A0]/20',
  Ready: 'bg-[#00B8CF]/15 text-[#00B8CF] border-[#00B8CF]/30',
  Generating: 'bg-accent/15 text-accent-hover border-accent/30',
  Review: 'bg-warning/15 text-warning border-warning/30',
  Approved: 'bg-success/15 text-success border-success/30',
  Exported: 'bg-[#2ecc71]/15 text-[#2ecc71] border-[#2ecc71]/30',
  Archived: 'bg-[#8B92A0]/10 text-text-dim border-[#8B92A0]/20',
}

const TONE_OPTIONS = [
  { value: 'professional', label: 'Professional' },
  { value: 'casual', label: 'Casual' },
  { value: 'bold', label: 'Bold' },
  { value: 'empathetic', label: 'Empathetic' },
]

const CHANNEL_ICONS: Record<string, string> = {
  linkedin_connect: 'LI',
  linkedin_message: 'LI',
  email: 'Em',
  call: 'Ph',
}

interface Props {
  campaign: CampaignDetailType
  onNavigate: (type: 'company' | 'contact', id: string) => void
}

export function CampaignDetail({ campaign, onNavigate }: Props) {
  const { toast } = useToast()
  const updateCampaign = useUpdateCampaign()
  const { data: contactsData, isLoading: contactsLoading } = useCampaignContacts(campaign.id)
  const { data: templateData } = useCampaignTemplates()
  const addContacts = useAddCampaignContacts()
  const removeContacts = useRemoveCampaignContacts()

  const [showPicker, setShowPicker] = useState(false)
  const [edits, setEdits] = useState<Record<string, unknown>>({})

  const contacts = useMemo(() => contactsData?.contacts ?? [], [contactsData])
  const templates = useMemo(() => templateData?.templates ?? [], [templateData])
  const isEditable = campaign.status === 'Draft' || campaign.status === 'Ready'

  // ── Field edits ──────────────────────────────────

  const handleFieldChange = useCallback((name: string, value: unknown) => {
    setEdits((prev) => ({ ...prev, [name]: value }))
  }, [])

  const hasChanges = Object.keys(edits).length > 0

  const handleSave = async () => {
    try {
      await updateCampaign.mutateAsync({ id: campaign.id, data: edits as Record<string, unknown> })
      toast('Campaign updated', 'success')
      setEdits({})
    } catch {
      toast('Failed to save changes', 'error')
    }
  }

  // ── Template config ──────────────────────────────

  const templateConfig: TemplateStep[] = useMemo(() => {
    return (campaign.template_config || []) as TemplateStep[]
  }, [campaign.template_config])

  const generationConfig = useMemo(() => {
    return (campaign.generation_config || {}) as Record<string, unknown>
  }, [campaign.generation_config])

  const handleLoadTemplate = useCallback(async (templateId: string) => {
    const tpl = templates.find((t) => t.id === templateId)
    if (!tpl) return
    try {
      await updateCampaign.mutateAsync({
        id: campaign.id,
        data: {
          template_config: tpl.steps,
          generation_config: tpl.default_config,
        },
      })
      toast('Template loaded', 'success')
    } catch {
      toast('Failed to load template', 'error')
    }
  }, [templates, campaign.id, updateCampaign, toast])

  const handleToggleStep = useCallback(async (stepIndex: number) => {
    const newConfig = [...templateConfig]
    newConfig[stepIndex] = { ...newConfig[stepIndex], enabled: !newConfig[stepIndex].enabled }
    try {
      await updateCampaign.mutateAsync({
        id: campaign.id,
        data: { template_config: newConfig },
      })
    } catch {
      toast('Failed to update step', 'error')
    }
  }, [templateConfig, campaign.id, updateCampaign, toast])

  const handleToneChange = useCallback(async (_: string, value: string) => {
    const newConfig = { ...generationConfig, tone: value }
    try {
      await updateCampaign.mutateAsync({
        id: campaign.id,
        data: { generation_config: newConfig },
      })
    } catch {
      toast('Failed to update tone', 'error')
    }
  }, [generationConfig, campaign.id, updateCampaign, toast])

  const handleInstructionsChange = useCallback(async (_: string, value: string) => {
    const newConfig = { ...generationConfig, custom_instructions: value }
    try {
      await updateCampaign.mutateAsync({
        id: campaign.id,
        data: { generation_config: newConfig },
      })
    } catch {
      toast('Failed to update instructions', 'error')
    }
  }, [generationConfig, campaign.id, updateCampaign, toast])

  // ── Contact management ──────────────────────────

  const handleAddContacts = useCallback(async (contactIds: string[]) => {
    try {
      const result = await addContacts.mutateAsync({
        campaignId: campaign.id,
        contactIds,
      })
      toast(`Added ${result.added} contact${result.added !== 1 ? 's' : ''}${result.skipped ? ` (${result.skipped} already assigned)` : ''}`, 'success')
      setShowPicker(false)
    } catch {
      toast('Failed to add contacts', 'error')
    }
  }, [campaign.id, addContacts, toast])

  const handleRemoveContact = useCallback(async (contactId: string) => {
    try {
      await removeContacts.mutateAsync({
        campaignId: campaign.id,
        contactIds: [contactId],
      })
      toast('Contact removed', 'success')
    } catch {
      toast('Failed to remove contact', 'error')
    }
  }, [campaign.id, removeContacts, toast])

  // ── Contact table columns ────────────────────────

  const contactColumns = useMemo(() => [
    {
      key: 'full_name' as const,
      label: 'Name',
      render: (c: CampaignContactItem) => (
        <button
          onClick={() => onNavigate('contact', c.contact_id)}
          className="text-sm text-accent-cyan hover:underline bg-transparent border-none cursor-pointer p-0 text-left"
        >
          {c.full_name || 'Unknown'}
        </button>
      ),
    },
    {
      key: 'job_title' as const,
      label: 'Title',
      render: (c: CampaignContactItem) => (
        <span className="text-xs text-text-muted">{c.job_title || '-'}</span>
      ),
    },
    {
      key: 'company_name' as const,
      label: 'Company',
      render: (c: CampaignContactItem) =>
        c.company_id ? (
          <button
            onClick={() => onNavigate('company', c.company_id!)}
            className="text-xs text-accent-cyan hover:underline bg-transparent border-none cursor-pointer p-0 text-left"
          >
            {c.company_name || '-'}
          </button>
        ) : (
          <span className="text-xs text-text-muted">-</span>
        ),
    },
    {
      key: 'status' as const,
      label: 'Status',
      render: (c: CampaignContactItem) => (
        <span className="text-xs text-text-muted">{c.status}</span>
      ),
    },
  ], [onNavigate])

  // ── Render ──────────────────────────────────────

  const statusColors = STATUS_COLORS[campaign.status] ?? STATUS_COLORS.Draft

  return (
    <div className="space-y-5 pb-6">
      {/* Status + save bar */}
      <div className="flex items-center justify-between">
        <span className={`inline-flex items-center px-2.5 py-1 text-xs font-medium rounded border ${statusColors}`}>
          {campaign.status}
        </span>
        {hasChanges && (
          <button
            onClick={handleSave}
            disabled={updateCampaign.isPending}
            className="px-3 py-1 text-xs font-medium rounded bg-accent text-white border-none cursor-pointer hover:bg-accent-hover transition-colors disabled:opacity-50"
          >
            {updateCampaign.isPending ? 'Saving...' : 'Save Changes'}
          </button>
        )}
      </div>

      {/* Overview fields */}
      <FieldGrid>
        <Field label="Contacts" value={campaign.total_contacts} />
        <Field label="Generated" value={`${campaign.generated_count}/${campaign.total_contacts}`} />
        <Field label="Cost" value={campaign.generation_cost > 0 ? `$${campaign.generation_cost.toFixed(2)}` : '-'} />
        <Field label="Owner" value={campaign.owner_name} />
      </FieldGrid>

      {/* Description (editable) */}
      {isEditable ? (
        <EditableTextarea
          label="Description"
          name="description"
          value={(edits.description as string) ?? campaign.description ?? ''}
          onChange={handleFieldChange}
          rows={2}
        />
      ) : (
        <Field label="Description" value={campaign.description} />
      )}

      <SectionDivider title="Message Sequence" />

      {/* Template loader (draft/ready only) */}
      {isEditable && templates.length > 0 && (
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs text-text-muted">Load template:</span>
          {templates.map((t) => (
            <button
              key={t.id}
              onClick={() => handleLoadTemplate(t.id)}
              className="px-2 py-0.5 text-xs rounded border border-border bg-surface text-text-muted hover:text-text hover:border-accent cursor-pointer transition-colors"
            >
              {t.name}
            </button>
          ))}
        </div>
      )}

      {/* Step list */}
      {templateConfig.length > 0 ? (
        <div className="space-y-1.5">
          {templateConfig.map((step, idx) => (
            <div
              key={idx}
              className={`flex items-center gap-3 px-3 py-2 rounded border transition-colors ${
                step.enabled
                  ? 'border-border bg-surface'
                  : 'border-border/50 bg-surface/50 opacity-50'
              }`}
            >
              {isEditable && (
                <button
                  onClick={() => handleToggleStep(idx)}
                  className={`w-4 h-4 rounded border flex items-center justify-center text-[10px] cursor-pointer transition-colors ${
                    step.enabled
                      ? 'bg-accent border-accent text-white'
                      : 'bg-transparent border-[#8B92A0]/40 text-transparent'
                  }`}
                >
                  {step.enabled ? '\u2713' : ''}
                </button>
              )}
              <span className="w-6 h-5 flex items-center justify-center text-[9px] font-bold text-text-muted bg-surface-alt rounded">
                {CHANNEL_ICONS[step.channel] || '?'}
              </span>
              <span className="text-sm text-text flex-1">{step.label}</span>
              <span className="text-xs text-text-dim">{step.channel.replace('_', ' ')}</span>
              {step.needs_pdf && (
                <span className="text-[10px] px-1.5 py-0.5 bg-accent/10 text-accent rounded">PDF</span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-text-muted">No message steps configured. Load a template above to get started.</p>
      )}

      {/* Generation config (tone + instructions) */}
      {templateConfig.length > 0 && (
        <div className="space-y-3 mt-4">
          {isEditable ? (
            <>
              <EditableSelect
                label="Tone"
                name="tone"
                value={(generationConfig.tone as string) || 'professional'}
                options={TONE_OPTIONS}
                onChange={handleToneChange}
              />
              <EditableTextarea
                label="Custom Instructions"
                name="custom_instructions"
                value={(generationConfig.custom_instructions as string) || ''}
                onChange={handleInstructionsChange}
                rows={3}
              />
            </>
          ) : (
            <FieldGrid>
              <Field label="Tone" value={(generationConfig.tone as string) || 'professional'} />
              <Field label="Custom Instructions" value={(generationConfig.custom_instructions as string) || '-'} />
            </FieldGrid>
          )}
        </div>
      )}

      <SectionDivider title={`Contacts (${contacts.length})`} />

      {/* Add contacts button */}
      {isEditable && (
        <div className="flex gap-2">
          <button
            onClick={() => setShowPicker(true)}
            className="px-3 py-1 text-xs font-medium rounded bg-accent text-white border-none cursor-pointer hover:bg-accent-hover transition-colors"
          >
            Add Contacts
          </button>
        </div>
      )}

      {/* Contact picker modal */}
      {showPicker && (
        <ContactPicker
          campaignId={campaign.id}
          existingContactIds={contacts.map((c) => c.contact_id)}
          onAdd={handleAddContacts}
          onClose={() => setShowPicker(false)}
          isLoading={addContacts.isPending}
        />
      )}

      {/* Contacts table */}
      {contactsLoading ? (
        <p className="text-xs text-text-muted">Loading contacts...</p>
      ) : contacts.length > 0 ? (
        <MiniTable
          columns={contactColumns}
          data={contacts}
          onRowAction={isEditable ? (c) => handleRemoveContact(c.contact_id) : undefined}
          actionLabel="Remove"
        />
      ) : (
        <p className="text-xs text-text-muted">No contacts assigned yet.</p>
      )}
    </div>
  )
}
