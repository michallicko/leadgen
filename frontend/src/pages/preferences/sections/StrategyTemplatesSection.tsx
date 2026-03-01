/**
 * StrategyTemplatesSection -- manage user + system strategy templates.
 *
 * Lists templates with name, category, created date.
 * User templates can be deleted (with confirmation).
 * System templates are visible but not deletable.
 */

import { useState } from 'react'
import {
  useStrategyTemplates,
  useDeleteStrategyTemplate,
  type StrategyTemplate,
} from '../../../api/queries/useStrategyTemplates'

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 4h12M5.33 4V2.67a1.33 1.33 0 0 1 1.34-1.34h2.66a1.33 1.33 0 0 1 1.34 1.34V4M6.67 7.33v4M9.33 7.33v4" />
      <path d="M3.33 4h9.34l-.67 9.33a1.33 1.33 0 0 1-1.33 1.34H5.33A1.33 1.33 0 0 1 4 13.33L3.33 4Z" />
    </svg>
  )
}

function SystemBadge() {
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded bg-accent/10 text-accent">
      System
    </span>
  )
}

function CategoryBadge({ category }: { category: string }) {
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded bg-accent-cyan/10 text-accent-cyan">
      {category}
    </span>
  )
}

function TemplateRow({
  template,
  onDelete,
}: {
  template: StrategyTemplate
  onDelete: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border border-border rounded-lg p-4 hover:border-border-solid transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium text-text truncate">{template.name}</span>
            {template.is_system && <SystemBadge />}
            {template.category && <CategoryBadge category={template.category} />}
          </div>
          {template.description && (
            <p className="text-xs text-text-muted line-clamp-2 mb-1">{template.description}</p>
          )}
          <p className="text-[10px] text-text-dim">
            {template.created_at
              ? new Date(template.created_at).toLocaleDateString()
              : ''}
          </p>
        </div>

        <div className="flex items-center gap-1 flex-shrink-0">
          {template.section_headers.length > 0 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="px-2 py-1 text-[10px] text-text-muted hover:text-text border border-border rounded transition-colors bg-transparent cursor-pointer"
            >
              {expanded ? 'Hide' : 'Preview'}
            </button>
          )}
          {!template.is_system && (
            <button
              onClick={() => onDelete(template.id)}
              className="p-1.5 text-text-dim hover:text-error transition-colors bg-transparent border-none cursor-pointer"
              title="Delete template"
            >
              <TrashIcon />
            </button>
          )}
        </div>
      </div>

      {expanded && template.section_headers.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border">
          <p className="text-[10px] font-medium text-text-muted mb-1.5 uppercase tracking-wider">
            Sections
          </p>
          <div className="flex flex-wrap gap-1.5">
            {template.section_headers.map((h) => (
              <span
                key={h}
                className="text-[11px] text-text-muted bg-surface-alt px-2 py-0.5 rounded"
              >
                {h}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function StrategyTemplatesSection() {
  const { data: templates, isLoading, isError } = useStrategyTemplates()
  const deleteMutation = useDeleteStrategyTemplate()
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  const handleDelete = (id: string) => {
    setConfirmDeleteId(id)
  }

  const confirmDelete = async () => {
    if (!confirmDeleteId) return
    await deleteMutation.mutateAsync(confirmDeleteId)
    setConfirmDeleteId(null)
  }

  const systemTemplates = templates?.filter((t) => t.is_system) || []
  const userTemplates = templates?.filter((t) => !t.is_system) || []

  return (
    <div className="space-y-6">
      <div className="bg-surface border border-border rounded-lg p-5">
        <h2 className="font-title text-[1rem] font-semibold tracking-tight mb-1">
          Strategy Templates
        </h2>
        <p className="text-text-muted text-xs mb-4">
          Pre-built GTM frameworks and your saved strategies. Select a template when
          starting a new playbook to get a structured starting point.
        </p>

        {isLoading && (
          <div className="flex items-center gap-2 py-6 justify-center">
            <div className="w-4 h-4 border-2 border-border border-t-accent rounded-full animate-spin" />
            <span className="text-sm text-text-muted">Loading templates...</span>
          </div>
        )}

        {isError && (
          <p className="text-sm text-error py-4 text-center">
            Failed to load templates.
          </p>
        )}

        {!isLoading && !isError && templates && (
          <div className="space-y-5">
            {systemTemplates.length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">
                  System Templates
                </h3>
                <div className="space-y-2">
                  {systemTemplates.map((t) => (
                    <TemplateRow key={t.id} template={t} onDelete={handleDelete} />
                  ))}
                </div>
              </div>
            )}

            <div>
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">
                Your Templates
              </h3>
              {userTemplates.length === 0 ? (
                <p className="text-xs text-text-dim py-3 text-center border border-dashed border-border rounded-lg">
                  No saved templates yet. Use &quot;Save as Template&quot; from your strategy
                  page to create one.
                </p>
              ) : (
                <div className="space-y-2">
                  {userTemplates.map((t) => (
                    <TemplateRow key={t.id} template={t} onDelete={handleDelete} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {confirmDeleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-surface border border-border-solid rounded-lg shadow-lg p-6 max-w-sm mx-4">
            <h3 className="text-sm font-semibold mb-2">Delete template?</h3>
            <p className="text-xs text-text-muted mb-4">
              This action cannot be undone. The template will be permanently removed.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setConfirmDeleteId(null)}
                className="px-3 py-1.5 text-xs font-medium rounded-md border border-border-solid text-text-muted hover:bg-surface-alt transition-colors bg-transparent cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleteMutation.isPending}
                className="px-3 py-1.5 text-xs font-medium rounded-md border border-error/30 text-error hover:bg-error/10 transition-colors bg-transparent cursor-pointer disabled:opacity-40"
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
