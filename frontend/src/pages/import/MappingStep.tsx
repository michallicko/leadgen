/**
 * MappingStep -- Step 2 of import wizard: column mapping with AI confidence indicators.
 */

import { useState, useCallback } from 'react'
import { submitPreview, remapWithAI } from '../../api/queries/useImports'
import type {
  ColumnMapping,
  UploadResponse,
  PreviewResponse,
} from '../../api/queries/useImports'

interface MappingStepProps {
  uploadResponse: UploadResponse
  mapping: ColumnMapping[]
  jobId: string
  onBack: () => void
  onPreviewComplete: (mapping: ColumnMapping[], preview: PreviewResponse) => void
  onRemapped: (response: UploadResponse) => void
}

/** Grouped target field options for the mapping dropdown */
const TARGET_OPTIONS: Array<{ value: string; label: string; group: string }> = [
  // Contact fields
  { value: 'first_name', label: 'First Name', group: 'Contact' },
  { value: 'last_name', label: 'Last Name', group: 'Contact' },
  { value: 'email', label: 'Email', group: 'Contact' },
  { value: 'phone', label: 'Phone', group: 'Contact' },
  { value: 'mobile', label: 'Mobile', group: 'Contact' },
  { value: 'job_title', label: 'Job Title', group: 'Contact' },
  { value: 'linkedin_url', label: 'LinkedIn URL', group: 'Contact' },
  { value: 'notes', label: 'Notes', group: 'Contact' },
  // Company fields
  { value: 'company_name', label: 'Company Name', group: 'Company' },
  { value: 'domain', label: 'Domain', group: 'Company' },
  { value: 'industry', label: 'Industry', group: 'Company' },
  { value: 'employee_count', label: 'Employee Count', group: 'Company' },
  { value: 'location', label: 'Location', group: 'Company' },
  { value: 'description', label: 'Description', group: 'Company' },
]

function ConfidenceDot({ level }: { level: 'high' | 'medium' | 'low' }) {
  const colors = {
    high: 'bg-green-400',
    medium: 'bg-amber-400',
    low: 'bg-red-400',
  }
  return <span className={`inline-block w-2 h-2 rounded-full ${colors[level]} mr-1.5`} />
}

/** Extract the bare field_key from a potentially dotted custom target like "contact.custom.X" → "X" */
function normalizeCustomTarget(target: string | null): string | null {
  if (!target) return null
  const parts = target.split('.')
  if (parts.length === 3 && parts[1] === 'custom') return parts[2]
  return target
}

export function MappingStep({
  uploadResponse,
  mapping: initialMapping,
  jobId,
  onBack,
  onPreviewComplete,
  onRemapped,
}: MappingStepProps) {
  // Filter out rows with empty/whitespace source column names (ghost rows from XLSX)
  // and normalize custom field target values to bare field_key format
  const cleanedInitial = initialMapping
    .filter((col) => col.source_column?.trim())
    .map((col) => ({
      ...col,
      target_field: normalizeCustomTarget(col.target_field),
    }))
  const [mapping, setMapping] = useState<ColumnMapping[]>(cleanedInitial)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isRemapping, setIsRemapping] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Custom field rename state: maps source_column -> edited display name
  const [customLabels, setCustomLabels] = useState<Record<string, string>>({})
  const [openPopover, setOpenPopover] = useState<string | null>(null)

  // Build set of known custom field keys for detecting is_custom in dropdown changes
  const customFieldKeys = new Set(uploadResponse.custom_field_defs.map((cf) => cf.field_key))
  const standardFieldKeys = new Set(TARGET_OPTIONS.map((o) => o.value))

  const handleTargetChange = useCallback((index: number, value: string) => {
    setMapping((prev) => {
      const updated = [...prev]
      const col = updated[index]
      if (value === '__new_custom__') {
        // Generate a field_key from source column name (snake_case)
        const fieldKey = col.source_column
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '_')
          .replace(/^_|_$/g, '')
        updated[index] = {
          ...col,
          target_field: fieldKey,
          is_custom: true,
          custom_display_name: col.source_column,
        }
      } else {
        updated[index] = {
          ...col,
          target_field: value || null,
          is_custom: value ? (customFieldKeys.has(value) || !standardFieldKeys.has(value)) : false,
          custom_display_name: customFieldKeys.has(value)
            ? uploadResponse.custom_field_defs.find((cf) => cf.field_key === value)?.display_name
            : undefined,
        }
      }
      return updated
    })
  }, [standardFieldKeys, customFieldKeys, uploadResponse.custom_field_defs])

  const handleCustomLabelChange = useCallback((sourceColumn: string, label: string) => {
    setCustomLabels((prev) => ({ ...prev, [sourceColumn]: label }))
  }, [])

  const handlePreview = useCallback(async () => {
    setError(null)
    setIsSubmitting(true)
    try {
      // Merge any custom label edits into the mapping before sending
      const finalMapping = mapping.map((col) => {
        const editedLabel = customLabels[col.source_column]
        if (editedLabel && col.is_custom) {
          return { ...col, custom_display_name: editedLabel }
        }
        return col
      })
      const preview = await submitPreview(jobId, finalMapping)
      onPreviewComplete(finalMapping, preview)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Preview failed')
    } finally {
      setIsSubmitting(false)
    }
  }, [jobId, mapping, customLabels, onPreviewComplete])

  const handleRemap = useCallback(async () => {
    setError(null)
    setIsRemapping(true)
    try {
      const response = await remapWithAI(jobId)
      // Clean and normalize the remapped columns the same way as initial mapping
      const cleaned = response.columns
        .filter((col) => col.source_column?.trim())
        .map((col) => ({
          ...col,
          target_field: normalizeCustomTarget(col.target_field),
        }))
      setMapping(cleaned)
      onRemapped(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Re-analysis failed')
    } finally {
      setIsRemapping(false)
    }
  }, [jobId, onRemapped])

  const warnings = uploadResponse.warnings

  return (
    <div>
      <h2 className="font-title text-sm font-semibold uppercase tracking-wider text-text-muted mb-4">
        Column Mapping
      </h2>

      {/* Warnings banner */}
      {warnings.length > 0 && (
        <div className="bg-amber-400/10 border border-amber-400/20 rounded-md px-4 py-3 mb-4">
          <strong className="text-amber-400 text-sm">Warnings:</strong>
          <ul className="mt-1 list-disc list-inside text-sm text-amber-400">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Mapping table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left py-2.5 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
                CSV Column
              </th>
              <th className="text-left py-2.5 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
                Sample Values
              </th>
              <th className="text-left py-2.5 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
                Target Field
              </th>
              <th className="text-left py-2.5 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
                Confidence
              </th>
            </tr>
          </thead>
          <tbody>
            {mapping.map((col, i) => (
              <tr key={col.source_column} className="border-b border-border/30">
                {/* Source column name */}
                <td className="py-2 px-3">
                  <strong className="text-text">{col.source_column}</strong>
                </td>

                {/* Sample values */}
                <td className="py-2 px-3">
                  <div className="text-text-muted text-xs max-w-[200px] truncate">
                    {col.sample_values.slice(0, 3).join(', ')}
                  </div>
                </td>

                {/* Target field select */}
                <td className="py-2 px-3">
                  <div className="flex items-center gap-1.5">
                    <select
                      value={col.target_field ?? ''}
                      onChange={(e) => handleTargetChange(i, e.target.value)}
                      className="bg-surface-alt border border-border rounded-md px-2 py-1.5 text-xs text-text focus:outline-none focus:border-accent-cyan"
                    >
                      <option value="">-- Skip --</option>
                      {/* If this row has a custom target_field that isn't in standard or custom_field_defs, render it */}
                      {col.is_custom && col.target_field && !customFieldKeys.has(col.target_field) && !standardFieldKeys.has(col.target_field) && (
                        <option value={col.target_field}>
                          {customLabels[col.source_column] || col.custom_display_name || col.target_field}
                        </option>
                      )}
                      {/* Contact fields */}
                      <optgroup label="Contact">
                        {TARGET_OPTIONS.filter((o) => o.group === 'Contact').map((o) => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </optgroup>
                      {/* Company fields */}
                      <optgroup label="Company">
                        {TARGET_OPTIONS.filter((o) => o.group === 'Company').map((o) => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </optgroup>
                      {/* Custom field defs from upload response */}
                      {uploadResponse.custom_field_defs.length > 0 && (
                        <optgroup label="Custom Fields">
                          {uploadResponse.custom_field_defs.map((cf) => (
                            <option key={cf.field_key} value={cf.field_key}>
                              {customLabels[cf.source_column] || cf.display_name || cf.field_key}
                            </option>
                          ))}
                        </optgroup>
                      )}
                      {/* Option to create a new custom field from this column */}
                      <optgroup label="Other">
                        <option value="__new_custom__">+ Create Custom Field</option>
                      </optgroup>
                    </select>

                    {/* Custom field badge + rename */}
                    {col.is_custom && (
                      <>
                        <span className="inline-block px-1.5 py-0.5 rounded text-[0.6rem] font-bold uppercase tracking-wider bg-accent-cyan/15 text-accent-cyan">
                          {col.custom_display_name ? 'Custom' : 'New'}
                        </span>
                        <div className="relative">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              setOpenPopover(openPopover === col.source_column ? null : col.source_column)
                            }}
                            className="inline-flex items-center justify-center w-5 h-5 border border-border-solid rounded text-text-muted text-xs hover:bg-surface-alt hover:text-accent-cyan transition-colors"
                            title="Edit field name"
                          >
                            &#9998;
                          </button>
                          {openPopover === col.source_column && (
                            <div className="absolute top-full left-0 mt-1 z-50 bg-surface border border-border-solid rounded-lg p-3 shadow-2xl shadow-black/40 min-w-[220px]">
                              <label className="block text-[0.68rem] font-semibold uppercase tracking-wider text-text-muted mb-1">
                                Field name
                              </label>
                              <input
                                type="text"
                                autoFocus
                                value={customLabels[col.source_column] ?? col.custom_display_name ?? ''}
                                onChange={(e) => handleCustomLabelChange(col.source_column, e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') setOpenPopover(null)
                                }}
                                className="w-full bg-surface-alt border border-border-solid rounded px-2 py-1 text-sm text-text focus:outline-none focus:border-accent-cyan"
                                placeholder="Field label"
                              />
                            </div>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                </td>

                {/* Confidence */}
                <td className="py-2 px-3">
                  <div className="flex items-center text-xs text-text-muted">
                    <ConfidenceDot level={col.confidence} />
                    {col.confidence}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Error */}
      {error && (
        <div className="mt-4 bg-red-400/10 border border-red-400/20 rounded-md px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3 mt-5">
        <button
          onClick={onBack}
          className="border border-border text-text-muted px-4 py-2 rounded-md hover:bg-surface-alt transition-colors text-sm"
        >
          Back
        </button>
        <button
          onClick={handlePreview}
          disabled={isSubmitting}
          className="bg-accent-cyan text-bg font-semibold px-4 py-2 rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
        >
          {isSubmitting ? 'Generating preview...' : 'Preview'}
        </button>
        <button
          onClick={handleRemap}
          disabled={isRemapping}
          className="ml-auto border border-border text-text-muted px-4 py-2 rounded-md hover:bg-surface-alt transition-colors text-sm disabled:opacity-50"
        >
          {isRemapping ? 'Analyzing...' : 'Re-analyze with AI'}
        </button>
      </div>
    </div>
  )
}
