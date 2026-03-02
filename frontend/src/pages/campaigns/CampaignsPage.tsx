import { useState, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router'
import {
  useCampaigns,
  useCampaignTemplates,
  useCreateCampaign,
  useDeleteCampaign,
  useCloneCampaign,
  type Campaign,
} from '../../api/queries/useCampaigns'
import { useOnboardingStatus } from '../../hooks/useOnboarding'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { CampaignsEmptyState } from '../../components/onboarding/SmartEmptyState'
import { useToast } from '../../components/ui/Toast'

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
  const navigate = useNavigate()
  const { data, isLoading } = useCampaigns()
  const { data: templateData } = useCampaignTemplates()
  const { data: onboardingStatus } = useOnboardingStatus()
  const createCampaign = useCreateCampaign()
  const deleteCampaign = useDeleteCampaign()
  const cloneCampaign = useCloneCampaign()
  const { toast } = useToast()

  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [newTemplateId, setNewTemplateId] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  const campaigns = useMemo(() => data?.campaigns ?? [], [data])
  const templates = useMemo(() => templateData?.templates ?? [], [templateData])

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

  const handleClone = useCallback(async (id: string) => {
    try {
      const result = await cloneCampaign.mutateAsync(id)
      toast(`Campaign cloned as '${result.name}'`, 'success')
      navigate(result.id)
    } catch {
      toast('Failed to clone campaign', 'error')
    }
  }, [cloneCampaign, toast, navigate])

  const handleDelete = useCallback((id: string) => {
    setDeleteTarget(id)
  }, [])

  const executeDelete = useCallback(async () => {
    if (!deleteTarget) return
    setDeleteTarget(null)
    await deleteCampaign.mutateAsync(deleteTarget)
  }, [deleteTarget, deleteCampaign])

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
        width: '90px',
        render: (c) => (
          <div className="flex items-center gap-1">
            <button
              onClick={(e) => {
                e.stopPropagation()
                handleClone(c.id)
              }}
              disabled={cloneCampaign.isPending}
              className="text-text-muted hover:text-accent text-xs bg-transparent border-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              title="Clone campaign"
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="5.5" y="5.5" width="9" height="9" rx="1.5" />
                <path d="M3 10.5H2.5a1 1 0 01-1-1v-7a1 1 0 011-1h7a1 1 0 011 1V3" />
              </svg>
            </button>
            {c.status === 'Draft' && (
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
            )}
          </div>
        ),
      },
    ],
    [handleDelete, handleClone, cloneCampaign.isPending],
  )

  // Show context-aware empty state when namespace has zero campaigns
  const namespaceHasNoCampaigns =
    onboardingStatus !== undefined && onboardingStatus.campaign_count === 0

  if (namespaceHasNoCampaigns && !isLoading && campaigns.length === 0) {
    return <CampaignsEmptyState />
  }

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
          onRowClick={(c) => navigate(c.id)}
        />
      </div>

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Delete campaign"
        message="Delete this draft campaign? This action cannot be undone."
        confirmLabel="Delete"
        variant="danger"
        onConfirm={executeDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
