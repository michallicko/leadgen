import { useState, useMemo, useCallback } from 'react'
import {
  useCampaigns,
  useCampaign,
  useCampaignTemplates,
  useCreateCampaign,
  useDeleteCampaign,
  type Campaign,
} from '../../api/queries/useCampaigns'
import { useEntityStack } from '../../hooks/useEntityStack'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { DetailModal } from '../../components/ui/DetailModal'
import { CampaignDetail } from './CampaignDetail'
import { ContactDetail } from '../contacts/ContactDetail'
import { useContact } from '../../api/queries/useContacts'
import { CompanyDetail } from '../companies/CompanyDetail'
import { useCompany } from '../../api/queries/useCompanies'

const CAMPAIGN_STATUS_COLORS: Record<string, string> = {
  Draft: 'bg-[#8B92A0]/10 text-text-muted border-[#8B92A0]/20',
  Ready: 'bg-[#00B8CF]/15 text-[#00B8CF] border-[#00B8CF]/30',
  Generating: 'bg-accent/15 text-accent-hover border-accent/30',
  Review: 'bg-warning/15 text-warning border-warning/30',
  Approved: 'bg-success/15 text-success border-success/30',
  Exported: 'bg-[#2ecc71]/15 text-[#2ecc71] border-[#2ecc71]/30',
  Archived: 'bg-[#8B92A0]/10 text-text-dim border-[#8B92A0]/20',
}

function StatusBadge({ value }: { value: string }) {
  const colors = CAMPAIGN_STATUS_COLORS[value] ?? CAMPAIGN_STATUS_COLORS.Draft
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border whitespace-nowrap ${colors}`}
    >
      {value}
    </span>
  )
}

export function CampaignsPage() {
  const { data, isLoading } = useCampaigns()
  const { data: templateData } = useCampaignTemplates()
  const createCampaign = useCreateCampaign()
  const deleteCampaign = useDeleteCampaign()

  // Entity stack for modal navigation
  const stack = useEntityStack('campaign')

  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [newTemplateId, setNewTemplateId] = useState('')

  const campaigns = useMemo(() => data?.campaigns ?? [], [data])
  const templates = useMemo(() => templateData?.templates ?? [], [templateData])

  // Detail data for whichever entity is at top of stack
  const isCampaignOpen = stack.current?.type === 'campaign'
  const isContactOpen = stack.current?.type === 'contact'
  const isCompanyOpen = stack.current?.type === 'company'

  const { data: campaignDetail, isLoading: campaignLoading } = useCampaign(
    isCampaignOpen ? stack.current!.id : null,
  )
  const { data: contactDetail, isLoading: contactLoading } = useContact(
    isContactOpen ? stack.current!.id : null,
  )
  const { data: companyDetail, isLoading: companyLoading } = useCompany(
    isCompanyOpen ? stack.current!.id : null,
  )

  const handleCreate = useCallback(async () => {
    if (!newName.trim()) return
    await createCampaign.mutateAsync({
      name: newName.trim(),
      description: newDesc.trim() || undefined,
      template_id: newTemplateId || undefined,
    })
    setNewName('')
    setNewDesc('')
    setNewTemplateId('')
    setShowCreate(false)
  }, [newName, newDesc, newTemplateId, createCampaign])

  const handleDelete = useCallback(
    async (id: string) => {
      if (!confirm('Delete this draft campaign?')) return
      await deleteCampaign.mutateAsync(id)
    },
    [deleteCampaign],
  )

  const columns: Column<Campaign>[] = useMemo(
    () => [
      {
        key: 'name',
        label: 'Name',
        width: '1fr',
        minWidth: '200px',
        render: (c) => (
          <span className="font-medium text-text">{c.name}</span>
        ),
      },
      {
        key: 'status',
        label: 'Status',
        width: '120px',
        render: (c) => <StatusBadge value={c.status} />,
      },
      {
        key: 'owner_name',
        label: 'Owner',
        width: '140px',
        render: (c) => (
          <span className="text-text-muted">{c.owner_name ?? '-'}</span>
        ),
      },
      {
        key: 'total_contacts',
        label: 'Contacts',
        width: '100px',
        render: (c) => (
          <span className="text-text-muted tabular-nums">{c.total_contacts}</span>
        ),
      },
      {
        key: 'generated_count',
        label: 'Generated',
        width: '100px',
        render: (c) => (
          <span className="text-text-muted tabular-nums">
            {c.generated_count}/{c.total_contacts}
          </span>
        ),
      },
      {
        key: 'generation_cost',
        label: 'Cost',
        width: '90px',
        render: (c) => (
          <span className="text-text-muted tabular-nums">
            {c.generation_cost > 0 ? `$${c.generation_cost.toFixed(2)}` : '-'}
          </span>
        ),
      },
      {
        key: 'created_at',
        label: 'Created',
        width: '140px',
        render: (c) => (
          <span className="text-text-muted text-xs">
            {c.created_at ? new Date(c.created_at).toLocaleDateString() : '-'}
          </span>
        ),
      },
      {
        key: 'actions',
        label: '',
        width: '60px',
        render: (c) =>
          c.status === 'Draft' ? (
            <button
              onClick={(e) => {
                e.stopPropagation()
                handleDelete(c.id)
              }}
              className="text-text-muted hover:text-error text-xs bg-transparent border-none cursor-pointer"
              title="Delete draft campaign"
            >
              Delete
            </button>
          ) : null,
      },
    ],
    [handleDelete],
  )

  // Modal title
  const modalTitle = isCampaignOpen
    ? (campaignDetail?.name ?? 'Campaign')
    : isContactOpen
      ? (contactDetail?.full_name ?? 'Contact')
      : isCompanyOpen
        ? (companyDetail?.name ?? 'Company')
        : ''

  const modalSubtitle = isCampaignOpen
    ? (campaignDetail?.description ?? undefined)
    : isContactOpen
      ? (contactDetail?.job_title ?? undefined)
      : isCompanyOpen
        ? (companyDetail?.domain ?? undefined)
        : undefined

  const modalLoading = isCampaignOpen
    ? campaignLoading
    : isContactOpen
      ? contactLoading
      : companyLoading

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <div>
          <h1 className="text-lg font-semibold text-text">Campaigns</h1>
          <p className="text-xs text-text-muted mt-0.5">
            {campaigns.length} campaign{campaigns.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-1.5 text-sm font-medium rounded-md bg-accent text-white border-none cursor-pointer hover:bg-accent-hover transition-colors"
        >
          New Campaign
        </button>
      </div>

      {/* Create dialog */}
      {showCreate && (
        <div className="px-6 py-4 bg-surface-alt border-b border-border">
          <div className="flex flex-col gap-3 max-w-lg">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Campaign name"
              className="px-3 py-1.5 text-sm rounded border border-border bg-surface text-text outline-none focus:border-accent"
              autoFocus
            />
            <input
              type="text"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="Description (optional)"
              className="px-3 py-1.5 text-sm rounded border border-border bg-surface text-text outline-none focus:border-accent"
            />
            {templates.length > 0 && (
              <select
                value={newTemplateId}
                onChange={(e) => setNewTemplateId(e.target.value)}
                className="px-3 py-1.5 text-sm rounded border border-border bg-surface text-text outline-none focus:border-accent cursor-pointer"
              >
                <option value="">No template (blank)</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} {t.is_system ? '(System)' : ''}
                  </option>
                ))}
              </select>
            )}
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                disabled={!newName.trim() || createCampaign.isPending}
                className="px-4 py-1.5 text-sm font-medium rounded-md bg-accent text-white border-none cursor-pointer hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {createCampaign.isPending ? 'Creating...' : 'Create'}
              </button>
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-1.5 text-sm rounded-md bg-transparent text-text-muted border border-border cursor-pointer hover:text-text transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="flex-1 overflow-hidden">
        <DataTable
          columns={columns}
          data={campaigns}
          isLoading={isLoading}
          emptyText="No campaigns yet. Click 'New Campaign' to create one."
          onRowClick={(c) => stack.open('campaign', c.id)}
        />
      </div>

      {/* Detail modal */}
      <DetailModal
        isOpen={!!stack.current}
        onClose={stack.close}
        title={modalTitle}
        subtitle={modalSubtitle}
        isLoading={modalLoading}
        canGoBack={stack.depth > 1}
        onBack={stack.pop}
        breadcrumb={stack.depth > 1 ? 'Back' : undefined}
      >
        {isCampaignOpen && campaignDetail && (
          <CampaignDetail campaign={campaignDetail} onNavigate={stack.push} />
        )}
        {isContactOpen && contactDetail && (
          <ContactDetail contact={contactDetail} onNavigate={stack.push} />
        )}
        {isCompanyOpen && companyDetail && (
          <CompanyDetail company={companyDetail} onNavigate={stack.push} />
        )}
      </DetailModal>
    </div>
  )
}
