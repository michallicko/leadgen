/**
 * VersionBrowser -- slide-out panel showing version history for a strategy document.
 *
 * Lists all versions (newest first) with author type icons, timestamps, and descriptions.
 * Clicking a version shows a read-only preview. "Restore" creates a new version from the
 * selected snapshot and updates the live document.
 */

import { useState, useCallback } from 'react'
import {
  usePlaybookVersions,
  usePlaybookVersionDetail,
  useRestoreVersion,
  type PlaybookVersion,
} from '../../api/queries/usePlaybook'

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function CloseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M4 4l8 8M12 4l-8 8" />
    </svg>
  )
}

function UserIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="5" r="3" />
      <path d="M2 14c0-3 2.5-5 6-5s6 2 6 5" />
    </svg>
  )
}

function AIIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 1l2 4 4.5 1-3.25 3 .75 4.5L8 11.5 3.96 13.5l.79-4.5L1.5 6l4.5-1L8 1z" />
    </svg>
  )
}

function HistoryIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1.5 8a6.5 6.5 0 1 1 1.28 3.88" />
      <path d="M1 4.5v4h4" />
      <path d="M8 4.5V8l2.5 1.5" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()

  if (diff < 60_000) return 'Just now'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`

  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// ---------------------------------------------------------------------------
// Version list item
// ---------------------------------------------------------------------------

interface VersionItemProps {
  version: PlaybookVersion
  isSelected: boolean
  onSelect: (id: string) => void
}

function VersionItem({ version, isSelected, onSelect }: VersionItemProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect(version.id)}
      className={`w-full text-left px-3 py-2.5 border-b border-border-solid transition-colors ${
        isSelected
          ? 'bg-accent/10 border-l-2 border-l-accent'
          : 'hover:bg-surface-alt border-l-2 border-l-transparent'
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className={`flex-shrink-0 ${version.author_type === 'ai' ? 'text-accent' : 'text-text-muted'}`}>
          {version.author_type === 'ai' ? <AIIcon /> : <UserIcon />}
        </span>
        <span className="text-xs font-medium text-text truncate">
          {version.description || `Version ${version.version_number}`}
        </span>
      </div>
      <div className="flex items-center gap-2 pl-[22px]">
        <span className="text-[10px] text-text-muted">
          v{version.version_number}
        </span>
        <span className="text-[10px] text-text-muted">
          {version.created_at ? formatDate(version.created_at) : ''}
        </span>
      </div>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Preview panel
// ---------------------------------------------------------------------------

interface PreviewPanelProps {
  documentId: string
  versionId: string
  onRestore: () => void
  isRestoring: boolean
}

function PreviewPanel({ documentId, versionId, onRestore, isRestoring }: PreviewPanelProps) {
  const { data: version, isLoading } = usePlaybookVersionDetail(documentId, versionId)

  if (isLoading) {
    return (
      <div className="p-4 text-sm text-text-muted">Loading version...</div>
    )
  }

  if (!version) {
    return (
      <div className="p-4 text-sm text-text-muted">Version not found</div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border-solid bg-surface-alt">
        <span className="text-xs font-medium text-text">
          v{version.version_number} preview
        </span>
        <button
          type="button"
          onClick={onRestore}
          disabled={isRestoring}
          className="px-3 py-1 text-xs font-medium rounded bg-accent text-white hover:bg-accent-hover disabled:opacity-50 transition-colors"
        >
          {isRestoring ? 'Restoring...' : 'Restore this version'}
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <pre className="whitespace-pre-wrap text-xs text-text font-mono leading-relaxed">
          {version.content || '(empty)'}
        </pre>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// VersionBrowser (main export)
// ---------------------------------------------------------------------------

interface VersionBrowserProps {
  documentId: string
  open: boolean
  onClose: () => void
}

export function VersionBrowser({ documentId, open, onClose }: VersionBrowserProps) {
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null)
  const { data: versions, isLoading } = usePlaybookVersions(documentId, open)
  const restoreMutation = useRestoreVersion(documentId)

  const handleRestore = useCallback(() => {
    if (!selectedVersionId) return
    restoreMutation.mutate(selectedVersionId, {
      onSuccess: () => {
        setSelectedVersionId(null)
        onClose()
      },
    })
  }, [selectedVersionId, restoreMutation, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/30"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="relative ml-auto w-full max-w-md bg-surface border-l border-border-solid shadow-xl flex flex-col transition-transform duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border-solid">
          <div className="flex items-center gap-2">
            <HistoryIcon />
            <h2 className="text-sm font-semibold text-text">Version History</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-surface-alt text-text-muted hover:text-text transition-colors"
          >
            <CloseIcon />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {selectedVersionId ? (
            <PreviewPanel
              documentId={documentId}
              versionId={selectedVersionId}
              onRestore={handleRestore}
              isRestoring={restoreMutation.isPending}
            />
          ) : (
            <div className="flex-1 overflow-y-auto">
              {isLoading && (
                <div className="p-4 text-sm text-text-muted">Loading versions...</div>
              )}
              {!isLoading && (!versions || versions.length === 0) && (
                <div className="p-4 text-sm text-text-muted">No versions yet. Versions are created automatically when AI edits are made.</div>
              )}
              {versions?.map((v) => (
                <VersionItem
                  key={v.id}
                  version={v}
                  isSelected={selectedVersionId === v.id}
                  onSelect={setSelectedVersionId}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer: back button when previewing */}
        {selectedVersionId && (
          <div className="border-t border-border-solid px-4 py-2">
            <button
              type="button"
              onClick={() => setSelectedVersionId(null)}
              className="text-xs text-text-muted hover:text-text transition-colors"
            >
              &larr; Back to version list
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
