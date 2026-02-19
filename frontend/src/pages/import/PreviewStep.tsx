/**
 * PreviewStep -- Step 3 of import wizard: preview rows, dedup strategy, and execute import.
 */

import { useState, useCallback } from 'react'
import { executeImport, googleExecute } from '../../api/queries/useImports'
import { ImportSuccess } from './ImportSuccess'
import type { PreviewResponse, ImportResponse } from '../../api/queries/useImports'

interface PreviewStepProps {
  previewResponse: PreviewResponse | null
  jobId: string
  source: 'csv' | 'google'
  dedupStrategy: 'skip' | 'update' | 'create_new'
  onDedupStrategyChange: (strategy: 'skip' | 'update' | 'create_new') => void
  onBack: () => void
  onImportComplete: (response: ImportResponse) => void
  importResponse: ImportResponse | null
  onReset: () => void
}

const DEDUP_OPTIONS: Array<{ value: 'skip' | 'update' | 'create_new'; label: string; description: string }> = [
  { value: 'skip', label: 'Skip duplicates', description: "Don't import rows that match existing contacts" },
  { value: 'update', label: 'Update existing', description: 'Update existing contact fields with imported data' },
  { value: 'create_new', label: 'Create new', description: 'Create new contacts even if duplicates exist' },
]

function StatusBadge({ status }: { status: 'new' | 'duplicate' | 'update' }) {
  const styles = {
    new: 'bg-green-400/15 text-green-400',
    duplicate: 'bg-amber-400/15 text-amber-400',
    update: 'bg-blue-400/15 text-blue-400',
  }
  const labels = {
    new: 'New',
    duplicate: 'Duplicate',
    update: 'Update',
  }
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[0.68rem] font-semibold uppercase ${styles[status]}`}>
      {labels[status]}
    </span>
  )
}

export function PreviewStep({
  previewResponse,
  jobId,
  source,
  dedupStrategy,
  onDedupStrategyChange,
  onBack,
  onImportComplete,
  importResponse,
  onReset,
}: PreviewStepProps) {
  const [isImporting, setIsImporting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleImport = useCallback(async () => {
    setError(null)
    setIsImporting(true)
    try {
      const response = source === 'google'
        ? await googleExecute(jobId, dedupStrategy)
        : await executeImport(jobId, dedupStrategy)
      onImportComplete(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setIsImporting(false)
    }
  }, [jobId, source, dedupStrategy, onImportComplete])

  // Show success panel if import completed
  if (importResponse) {
    return (
      <ImportSuccess
        response={importResponse}
        jobId={jobId}
        onReset={onReset}
      />
    )
  }

  if (!previewResponse) {
    return (
      <div className="flex items-center justify-center gap-3 p-8 text-text-muted">
        <div className="w-6 h-6 border-2 border-border border-t-accent-cyan rounded-full animate-spin" />
        <span className="text-sm">Loading preview...</span>
      </div>
    )
  }

  const { total_rows, new_contacts, duplicates, new_companies, preview_rows } = previewResponse

  return (
    <div>
      <h2 className="font-title text-sm font-semibold uppercase tracking-wider text-text-muted mb-4">
        Preview
      </h2>

      {/* Summary bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <div className="bg-surface-alt rounded-lg p-4 text-center">
          <div className="font-title text-xl font-bold text-text">{total_rows}</div>
          <div className="text-[0.7rem] text-text-muted uppercase tracking-wider mt-1">Total Rows</div>
        </div>
        <div className="bg-surface-alt rounded-lg p-4 text-center">
          <div className="font-title text-xl font-bold text-green-400">{new_contacts}</div>
          <div className="text-[0.7rem] text-text-muted uppercase tracking-wider mt-1">New Contacts</div>
        </div>
        <div className="bg-surface-alt rounded-lg p-4 text-center">
          <div className="font-title text-xl font-bold text-amber-400">{duplicates}</div>
          <div className="text-[0.7rem] text-text-muted uppercase tracking-wider mt-1">Duplicates</div>
        </div>
        <div className="bg-surface-alt rounded-lg p-4 text-center">
          <div className="font-title text-xl font-bold text-green-400">{new_companies}</div>
          <div className="text-[0.7rem] text-text-muted uppercase tracking-wider mt-1">New Companies</div>
        </div>
      </div>

      {/* Preview table */}
      <div className="max-h-[400px] overflow-auto border border-border rounded-lg mb-5">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface z-10">
            <tr className="border-b border-border">
              <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted whitespace-nowrap">Row #</th>
              <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted whitespace-nowrap">Name</th>
              <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted whitespace-nowrap">Email</th>
              <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted whitespace-nowrap">Company</th>
              <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted whitespace-nowrap">Status</th>
            </tr>
          </thead>
          <tbody>
            {preview_rows.map((row) => (
              <tr key={row.row_number} className="border-b border-border/30">
                <td className="py-2 px-3 text-text-muted">{row.row_number}</td>
                <td className="py-2 px-3 text-text max-w-[160px] truncate">
                  {row.data.first_name || row.data.name || ''} {row.data.last_name || ''}
                </td>
                <td className="py-2 px-3 text-text max-w-[180px] truncate">
                  {row.data.email || row.data.email_address || ''}
                </td>
                <td className="py-2 px-3 text-text max-w-[160px] truncate">
                  {row.data.company || row.data.company_name || ''}
                </td>
                <td className="py-2 px-3">
                  <StatusBadge status={row.status} />
                </td>
              </tr>
            ))}
            {preview_rows.length === 0 && (
              <tr>
                <td colSpan={5} className="py-6 text-center text-text-dim text-sm">
                  No preview rows available
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Dedup strategy */}
      <div className="mb-5">
        <label className="block text-xs text-text-muted font-medium mb-2">
          Duplicate Strategy
        </label>
        <div className="flex flex-wrap gap-2">
          {DEDUP_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className={`flex items-center gap-2 px-4 py-2 rounded-md border cursor-pointer text-sm transition-colors ${
                dedupStrategy === opt.value
                  ? 'border-accent-cyan text-text bg-accent-cyan/5'
                  : 'border-border text-text-muted hover:border-accent-cyan hover:text-text'
              }`}
            >
              <input
                type="radio"
                name="dedup"
                value={opt.value}
                checked={dedupStrategy === opt.value}
                onChange={() => onDedupStrategyChange(opt.value)}
                className="hidden"
              />
              <span>{opt.label}</span>
            </label>
          ))}
        </div>
        <p className="text-xs text-text-dim mt-1.5">
          {DEDUP_OPTIONS.find((o) => o.value === dedupStrategy)?.description}
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 bg-red-400/10 border border-red-400/20 rounded-md px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="border border-border text-text-muted px-4 py-2 rounded-md hover:bg-surface-alt transition-colors text-sm"
        >
          Back
        </button>
        <button
          onClick={handleImport}
          disabled={isImporting}
          className="bg-accent-cyan text-bg font-semibold px-5 py-2.5 rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
        >
          {isImporting ? (
            <span className="flex items-center gap-2">
              <span className="w-4 h-4 border-2 border-bg/30 border-t-bg rounded-full animate-spin" />
              Importing...
            </span>
          ) : (
            `Import ${new_contacts + duplicates} Contacts`
          )}
        </button>
      </div>
    </div>
  )
}
