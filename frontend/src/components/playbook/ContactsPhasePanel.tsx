/**
 * ContactsPhasePanel — embedded filtered contacts list for the Contacts phase
 * of the playbook. Reuses DataTable with checkbox selection and shows
 * ICP-derived filters pre-applied from the strategy document.
 */

import { useState, useMemo, useCallback } from 'react'
import {
  usePlaybookContacts,
  useConfirmContactSelection,
  type PlaybookContactsFilters,
} from '../../api/queries/usePlaybookContacts'
import { DataTable, type Column } from '../ui/DataTable'

// ── Types ────────────────────────────────────────────────────

interface ContactsPhaseProps {
  extractedData: Record<string, unknown>
  existingSelections?: string[]
}

interface ContactRow {
  id: string
  full_name: string
  first_name: string
  last_name: string
  job_title: string | null
  company_name: string | null
  email_address: string | null
  seniority_level: string | null
  contact_score: number | null
  icp_fit: string | null
}

// ── Columns ──────────────────────────────────────────────────

const COLUMNS: Column<ContactRow>[] = [
  {
    key: 'full_name',
    label: 'Name',
    sortKey: 'last_name',
    width: '180px',
    render: (c) => (
      <span className="font-medium text-text">{c.full_name}</span>
    ),
  },
  {
    key: 'company_name',
    label: 'Company',
    width: '150px',
    render: (c) => (
      <span className="text-text-muted">{c.company_name ?? '--'}</span>
    ),
  },
  {
    key: 'job_title',
    label: 'Job Title',
    sortKey: 'job_title',
    width: '160px',
    render: (c) => (
      <span className="text-text-muted truncate">{c.job_title ?? '--'}</span>
    ),
  },
  {
    key: 'seniority_level',
    label: 'Seniority',
    sortKey: 'seniority_level',
    width: '110px',
    render: (c) => (
      <span className="text-text-muted text-xs">{c.seniority_level ?? '--'}</span>
    ),
  },
  {
    key: 'contact_score',
    label: 'Score',
    sortKey: 'contact_score',
    width: '70px',
    render: (c) => (
      <span className="tabular-nums text-text-muted">
        {c.contact_score != null ? c.contact_score : '--'}
      </span>
    ),
  },
  {
    key: 'icp_fit',
    label: 'ICP Fit',
    width: '90px',
    render: (c) => <IcpBadge fit={c.icp_fit} />,
  },
]

function IcpBadge({ fit }: { fit: string | null }) {
  if (!fit || fit === 'unknown') {
    return <span className="text-text-dim text-xs">--</span>
  }
  const color =
    fit === 'strong_fit' || fit === 'Strong Fit'
      ? 'text-green-400'
      : fit === 'moderate_fit' || fit === 'Moderate Fit'
        ? 'text-amber-400'
        : 'text-text-dim'
  const label = fit.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  return <span className={`text-xs font-medium ${color}`}>{label}</span>
}

// ── Filter chips ─────────────────────────────────────────────

function FilterChips({
  filters,
  onRemove,
}: {
  filters: PlaybookContactsFilters
  onRemove: (key: keyof PlaybookContactsFilters, value: string) => void
}) {
  const chips: { key: keyof PlaybookContactsFilters; label: string; value: string }[] = []

  const labelMap: Record<keyof PlaybookContactsFilters, string> = {
    industries: 'Industry',
    seniority_levels: 'Seniority',
    geo_regions: 'Region',
    company_sizes: 'Size',
  }

  for (const [key, values] of Object.entries(filters)) {
    if (!Array.isArray(values)) continue
    const k = key as keyof PlaybookContactsFilters
    for (const v of values) {
      chips.push({ key: k, label: labelMap[k] || key, value: v })
    }
  }

  if (chips.length === 0) return null

  return (
    <div className="flex flex-wrap gap-1.5">
      {chips.map((chip) => (
        <span
          key={`${chip.key}-${chip.value}`}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-accent/10 text-accent text-[11px] font-medium"
        >
          <span className="text-text-dim">{chip.label}:</span>
          {chip.value}
          <button
            type="button"
            onClick={() => onRemove(chip.key, chip.value)}
            className="ml-0.5 hover:text-red-400 transition-colors"
            aria-label={`Remove ${chip.label}: ${chip.value}`}
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M2.5 2.5l5 5M7.5 2.5l-5 5" />
            </svg>
          </button>
        </span>
      ))}
    </div>
  )
}

// ── Main component ───────────────────────────────────────────

export function ContactsPhasePanel({ extractedData, existingSelections }: ContactsPhaseProps) {
  // Filter state (initially derived from ICP, user can modify)
  const [filterOverrides, setFilterOverrides] = useState<PlaybookContactsFilters>({})
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [sortField, setSortField] = useState('last_name')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(
    () => new Set(existingSelections ?? []),
  )

  // Determine if we have ICP data
  const icp = extractedData?.icp as Record<string, unknown> | undefined
  const hasIcp = Boolean(icp && Object.keys(icp).length > 0)

  // Active filters = overrides if set (user can clear ICP filters)
  const activeFilters = filterOverrides

  const { data, isLoading, isFetching } = usePlaybookContacts(activeFilters, {
    page,
    per_page: 25,
    sort: sortField,
    sort_dir: sortDir,
    search,
    enabled: true,
  })

  const confirmMutation = useConfirmContactSelection()

  // Use ICP-derived filters as initial state on first load
  const [initializedFromIcp, setInitializedFromIcp] = useState(false)
  if (data && !initializedFromIcp && Object.keys(filterOverrides).length === 0) {
    const applied = data.filters.applied_filters
    if (applied && Object.keys(applied).length > 0) {
      setFilterOverrides(applied)
    }
    setInitializedFromIcp(true)
  }

  const contacts = useMemo(() => data?.contacts ?? [], [data])
  const total = data?.total ?? 0
  const icpSource = data?.icp_source ?? false

  // Handlers
  const handleSort = useCallback((field: string, dir: 'asc' | 'desc') => {
    setSortField(field)
    setSortDir(dir)
  }, [])

  const handleSelectionChange = useCallback((ids: Set<string>) => {
    setSelectedIds(ids)
  }, [])

  const handleRemoveFilter = useCallback(
    (key: keyof PlaybookContactsFilters, value: string) => {
      setFilterOverrides((prev) => {
        const updated = { ...prev }
        const arr = updated[key] ?? []
        updated[key] = arr.filter((v) => v !== value)
        if (updated[key]!.length === 0) {
          delete updated[key]
        }
        return updated
      })
      setPage(1)
    },
    [],
  )

  const handleClearAllFilters = useCallback(() => {
    setFilterOverrides({})
    setPage(1)
  }, [])

  const handleConfirm = useCallback(() => {
    const ids = Array.from(selectedIds)
    if (ids.length === 0) return
    confirmMutation.mutate(ids)
  }, [selectedIds, confirmMutation])

  const handleSearchChange = useCallback((value: string) => {
    setSearch(value)
    setPage(1)
  }, [])

  const activeFilterCount = Object.values(activeFilters).reduce(
    (sum, arr) => sum + (Array.isArray(arr) ? arr.length : 0),
    0,
  )

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* ICP banner when no ICP data */}
      {!hasIcp && (
        <div className="mx-3 mt-2 px-3 py-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
          <div className="flex items-center gap-2">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="text-amber-400 flex-shrink-0">
              <path d="M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM8 5v3M8 10h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <p className="text-xs text-amber-200/80">
              Extract your ICP from the Strategy phase to auto-filter contacts.
              Showing all contacts for now.
            </p>
          </div>
        </div>
      )}

      {/* Header: search + filter chips + count */}
      <div className="px-3 pt-2 pb-1 space-y-2">
        <div className="flex items-center gap-2">
          {/* Search input */}
          <div className="relative flex-1 max-w-xs">
            <svg
              width="14" height="14" viewBox="0 0 14 14" fill="none"
              className="absolute left-2 top-1/2 -translate-y-1/2 text-text-dim"
            >
              <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.2" />
              <path d="M9.5 9.5L12.5 12.5" stroke="currentColor" strokeWidth="1.2" />
            </svg>
            <input
              type="text"
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Search contacts..."
              className="w-full pl-7 pr-2 py-1.5 text-xs bg-surface-alt border border-border-solid rounded-md text-text placeholder:text-text-dim focus:outline-none focus:border-accent"
            />
          </div>

          <span className="text-xs text-text-muted whitespace-nowrap">
            {total.toLocaleString()} contact{total !== 1 ? 's' : ''}
            {icpSource && activeFilterCount > 0 && (
              <span className="text-accent ml-1">(ICP filtered)</span>
            )}
          </span>

          {activeFilterCount > 0 && (
            <button
              type="button"
              onClick={handleClearAllFilters}
              className="text-[10px] text-text-dim hover:text-accent transition-colors whitespace-nowrap"
            >
              Clear filters
            </button>
          )}
        </div>

        {/* Filter chips */}
        <FilterChips filters={activeFilters} onRemove={handleRemoveFilter} />
      </div>

      {/* Data table */}
      <div className="flex-1 min-h-0 px-3">
        <DataTable
          columns={COLUMNS}
          data={contacts}
          sort={{ field: sortField, dir: sortDir }}
          onSort={handleSort}
          isLoading={isLoading || isFetching}
          emptyText={
            hasIcp
              ? 'No contacts match your ICP criteria. Try adjusting filters.'
              : 'No contacts found. Import contacts first.'
          }
          selectable
          selectedIds={selectedIds}
          onSelectionChange={handleSelectionChange}
          totalMatching={total}
        />
      </div>

      {/* Pagination */}
      {(data?.pages ?? 0) > 1 && (
        <div className="flex items-center justify-center gap-2 px-3 py-2 border-t border-border-solid">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="px-2 py-1 text-xs rounded border border-border-solid text-text-muted hover:text-text disabled:opacity-40 transition-colors"
          >
            Prev
          </button>
          <span className="text-xs text-text-dim">
            Page {page} of {data?.pages ?? 1}
          </span>
          <button
            type="button"
            disabled={page >= (data?.pages ?? 1)}
            onClick={() => setPage((p) => p + 1)}
            className="px-2 py-1 text-xs rounded border border-border-solid text-text-muted hover:text-text disabled:opacity-40 transition-colors"
          >
            Next
          </button>
        </div>
      )}

      {/* Footer: selection count + confirm button */}
      <div className="flex items-center justify-between px-3 py-2.5 border-t border-border-solid bg-surface-alt/50">
        <span className="text-xs text-text-muted">
          {selectedIds.size > 0
            ? `${selectedIds.size} contact${selectedIds.size !== 1 ? 's' : ''} selected`
            : 'Select contacts to include in outreach'}
        </span>
        <button
          type="button"
          disabled={selectedIds.size === 0 || confirmMutation.isPending}
          onClick={handleConfirm}
          className="px-4 py-1.5 text-xs font-medium rounded-lg bg-accent text-bg hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
        >
          {confirmMutation.isPending ? (
            <>
              <div className="w-3 h-3 border-2 border-bg/30 border-t-bg rounded-full animate-spin" />
              Confirming...
            </>
          ) : (
            <>
              Confirm Selection
              {selectedIds.size > 0 && (
                <span className="px-1.5 py-0.5 rounded bg-bg/20 text-[10px]">
                  {selectedIds.size}
                </span>
              )}
            </>
          )}
        </button>
      </div>

      {/* Error display */}
      {confirmMutation.isError && (
        <div className="mx-3 mb-2 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400">
          Failed to confirm selection. Please try again.
        </div>
      )}
    </div>
  )
}
