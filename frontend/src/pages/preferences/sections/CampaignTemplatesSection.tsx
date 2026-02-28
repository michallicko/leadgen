/**
 * CampaignTemplatesSection -- manage campaign templates (BL-037).
 * Lists all templates (system + tenant), allows rename and delete of tenant-owned.
 */

import { useState, useCallback } from 'react'
import {
  useCampaignTemplates,
  useUpdateCampaignTemplate,
  useDeleteCampaignTemplate,
  type CampaignTemplate,
} from '../../../api/queries/useCampaigns'
import { useToast } from '../../../components/ui/Toast'
import { ConfirmDialog } from '../../../components/ui/ConfirmDialog'

export function CampaignTemplatesSection() {
  const { data, isLoading } = useCampaignTemplates()
  const updateTemplate = useUpdateCampaignTemplate()
  const deleteTemplate = useDeleteCampaignTemplate()
  const { toast } = useToast()

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<CampaignTemplate | null>(null)

  const templates = data?.templates ?? []

  const startEditing = useCallback((tpl: CampaignTemplate) => {
    setEditingId(tpl.id)
    setEditName(tpl.name)
  }, [])

  const saveEdit = useCallback(async () => {
    if (!editingId || !editName.trim()) return
    try {
      await updateTemplate.mutateAsync({ id: editingId, data: { name: editName.trim() } })
      toast('Template renamed', 'success')
      setEditingId(null)
    } catch {
      toast('Failed to rename template', 'error')
    }
  }, [editingId, editName, updateTemplate, toast])

  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return
    try {
      await deleteTemplate.mutateAsync(deleteTarget.id)
      toast('Template deleted', 'success')
    } catch {
      toast('Failed to delete template', 'error')
    }
    setDeleteTarget(null)
  }, [deleteTarget, deleteTemplate, toast])

  if (isLoading) {
    return (
      <div className="bg-surface border border-border rounded-lg p-5">
        <h2 className="font-title text-[1rem] font-semibold tracking-tight mb-4">
          Campaign Templates
        </h2>
        <div className="flex items-center justify-center py-8">
          <div className="w-5 h-5 border-2 border-border border-t-accent rounded-full animate-spin" />
        </div>
      </div>
    )
  }

  return (
    <div className="bg-surface border border-border rounded-lg p-5">
      <h2 className="font-title text-[1rem] font-semibold tracking-tight mb-4">
        Campaign Templates
      </h2>

      {templates.length === 0 ? (
        <p className="text-text-muted text-sm">
          No custom templates yet. Save a campaign as a template to get started.
        </p>
      ) : (
        <div className="space-y-0">
          {/* Header */}
          <div className="grid grid-cols-[1fr_80px_140px_80px] gap-3 px-3 py-2 text-xs text-text-muted font-medium border-b border-border">
            <span>Name</span>
            <span>Steps</span>
            <span>Created</span>
            <span />
          </div>

          {/* Rows */}
          {templates.map((tpl) => (
            <div
              key={tpl.id}
              className="grid grid-cols-[1fr_80px_140px_80px] gap-3 px-3 py-2.5 items-center border-b border-border/50 last:border-b-0 hover:bg-surface-alt/50 transition-colors"
            >
              {/* Name (editable inline) */}
              <div className="flex items-center gap-2 min-w-0">
                {editingId === tpl.id ? (
                  <div className="flex items-center gap-1.5 flex-1 min-w-0">
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveEdit()
                        if (e.key === 'Escape') setEditingId(null)
                      }}
                      className="flex-1 min-w-0 px-2 py-0.5 text-sm rounded border border-accent bg-surface text-text outline-none"
                      autoFocus
                    />
                    <button
                      onClick={saveEdit}
                      disabled={!editName.trim() || updateTemplate.isPending}
                      className="text-xs text-accent hover:text-accent-hover bg-transparent border-none cursor-pointer disabled:opacity-50"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="text-xs text-text-muted hover:text-text bg-transparent border-none cursor-pointer"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm text-text truncate">{tpl.name}</span>
                    {tpl.is_system && (
                      <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded bg-accent/10 text-accent border border-accent/20 whitespace-nowrap flex-shrink-0">
                        System
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Step count */}
              <span className="text-sm text-text-muted tabular-nums">
                {tpl.steps?.length ?? 0}
              </span>

              {/* Created date */}
              <span className="text-xs text-text-muted">
                {tpl.created_at ? new Date(tpl.created_at).toLocaleDateString() : '-'}
              </span>

              {/* Actions */}
              <div className="flex items-center gap-2">
                {!tpl.is_system && editingId !== tpl.id && (
                  <>
                    <button
                      onClick={() => startEditing(tpl)}
                      className="text-xs text-text-muted hover:text-accent bg-transparent border-none cursor-pointer"
                      title="Rename template"
                    >
                      Rename
                    </button>
                    <button
                      onClick={() => setDeleteTarget(tpl)}
                      className="text-xs text-text-muted hover:text-error bg-transparent border-none cursor-pointer"
                      title="Delete template"
                    >
                      Delete
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Delete template"
        message={`Delete "${deleteTarget?.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
