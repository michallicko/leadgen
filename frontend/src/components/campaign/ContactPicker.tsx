import { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { FilterBar, type FilterConfig } from '../ui/FilterBar.tsx'
import { SelectionActionBar } from '../ui/SelectionActionBar.tsx'
import { useAvailableContacts, type PickerContact, type PickerFilters } from '../../api/queries/useCampaignContacts.ts'
import { useTags } from '../../api/queries/useTags.ts'
import { useAddCampaignContacts, useRemoveCampaignContacts } from '../../api/queries/useCampaigns.ts'
import { useToast } from '../ui/Toast.tsx'
import {
  STATUS_DISPLAY,
  INDUSTRY_DISPLAY,
  filterOptions,
} from '../../lib/display.ts'

// ── Constants ──────────────────────────────────────────

const ENRICHMENT_BADGE: Record<string, { label: string; classes: string }> = {
  L2: {
    label: 'L2',
    classes: 'bg-success/15 text-success border-success/30',
  },
  L1: {
    label: 'L1',
    classes: 'bg-warning/15 text-warning border-warning/30',
  },
  None: {
    label: 'None',
    classes: 'bg-[#8B92A0]/10 text-text-dim border-[#8B92A0]/20',
  },
}

type SortField = 'name' | 'company' | 'enrichment' | 'score'
type SortDir = 'asc' | 'desc'

// ── Props ──────────────────────────────────────────────

interface ContactPickerProps {
  campaignId: string
  selectedContactIds: string[]
  onSelectionChange: (contactIds: string[]) => void
}

// ── Component ──────────────────────────────────────────

export function ContactPicker({
  campaignId,
  selectedContactIds,
  onSelectionChange,
}: ContactPickerProps) {
  const { toast } = useToast()

  // Filter state
  const [owner, setOwner] = useState('')
  const [tag, setTag] = useState('')
  const [industry, setIndustry] = useState('')
  const [companyStatus, setCompanyStatus] = useState('')
  const [search, setSearch] = useState('')
  const [enrichmentReady, setEnrichmentReady] = useState(false)

  // Sort state
  const [sortField, setSortField] = useState<SortField>('name')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  // Selection as a Set for O(1) lookups
  const selectedSet = useMemo(
    () => new Set(selectedContactIds),
    [selectedContactIds],
  )

  // Build filters for the query
  const queryFilters = useMemo<PickerFilters>(() => ({
    search: search || undefined,
    owner_name: owner || undefined,
    tag_name: tag || undefined,
    industry: industry || undefined,
    company_status: companyStatus || undefined,
    enrichment_ready: enrichmentReady || undefined,
    exclude_campaign_id: campaignId,
    sort: sortField === 'name' ? 'last_name' : undefined,
    sort_dir: sortDir,
  }), [search, owner, tag, industry, companyStatus, enrichmentReady, campaignId, sortField, sortDir])

  // Queries
  const {
    data,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useAvailableContacts(queryFilters)

  const { data: tagsData } = useTags()
  const addContacts = useAddCampaignContacts()
  const removeContacts = useRemoveCampaignContacts()

  // Flatten infinite query pages
  const allContacts = useMemo(() => {
    if (!data?.pages) return []
    return data.pages.flatMap((p) => p.contacts)
  }, [data])

  // Client-side sort (server only supports last_name sort)
  const sortedContacts = useMemo(() => {
    const sorted = [...allContacts]
    sorted.sort((a, b) => {
      let cmp = 0
      switch (sortField) {
        case 'name':
          cmp = a.full_name.localeCompare(b.full_name)
          break
        case 'company':
          cmp = (a.company_name ?? '').localeCompare(b.company_name ?? '')
          break
        case 'enrichment': {
          const order = { L2: 0, L1: 1, None: 2 }
          cmp = order[a.enrichment_level] - order[b.enrichment_level]
          break
        }
        case 'score':
          cmp = (a.contact_score ?? 0) - (b.contact_score ?? 0)
          break
      }
      return sortDir === 'desc' ? -cmp : cmp
    })
    return sorted
  }, [allContacts, sortField, sortDir])

  // Total from the first page (API total, not just loaded contacts)
  const totalCount = data?.pages[0]?.total ?? 0

  // Infinite scroll sentinel
  const sentinelRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage()
        }
      },
      { rootMargin: '200px' },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  // Build filter dropdown options
  const ownerOptions = useMemo(() =>
    (tagsData?.owners ?? []).map((o) => ({ value: o.name, label: o.name })),
    [tagsData],
  )

  const tagOptions = useMemo(() =>
    (tagsData?.tags ?? []).map((t) => ({ value: t.name, label: t.name })),
    [tagsData],
  )

  const statusOptions = useMemo(() => filterOptions(STATUS_DISPLAY), [])
  const industryOptions = useMemo(() => filterOptions(INDUSTRY_DISPLAY), [])

  // Handle sort click
  const handleSort = useCallback((field: SortField) => {
    setSortField((prev) => {
      if (prev === field) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
        return field
      }
      setSortDir('asc')
      return field
    })
  }, [])

  // Filter change handler
  const handleFilterChange = useCallback((key: string, value: string) => {
    switch (key) {
      case 'owner': setOwner(value); break
      case 'tag': setTag(value); break
      case 'industry': setIndustry(value); break
      case 'companyStatus': setCompanyStatus(value); break
      case 'search': setSearch(value); break
    }
  }, [])

  // Selection handlers
  const toggleSelect = useCallback((id: string) => {
    const next = new Set(selectedSet)
    if (next.has(id)) {
      next.delete(id)
    } else {
      next.add(id)
    }
    onSelectionChange(Array.from(next))
  }, [selectedSet, onSelectionChange])

  const toggleSelectAll = useCallback(() => {
    const visibleIds = sortedContacts.map((c) => c.id)
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedSet.has(id))
    if (allSelected) {
      // Deselect all visible
      const next = new Set(selectedSet)
      for (const id of visibleIds) {
        next.delete(id)
      }
      onSelectionChange(Array.from(next))
    } else {
      // Select all visible
      const next = new Set(selectedSet)
      for (const id of visibleIds) {
        next.add(id)
      }
      onSelectionChange(Array.from(next))
    }
  }, [sortedContacts, selectedSet, onSelectionChange])

  // Keyboard shortcut: Cmd/Ctrl+A
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'a') {
        const tag = (e.target as HTMLElement)?.tagName
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
        e.preventDefault()
        const allIds = sortedContacts.map((c) => c.id)
        const next = new Set(selectedSet)
        for (const id of allIds) {
          next.add(id)
        }
        onSelectionChange(Array.from(next))
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [sortedContacts, selectedSet, onSelectionChange])

  // Add selected contacts to campaign
  const handleAddToCampaign = useCallback(async () => {
    if (selectedContactIds.length === 0) return
    try {
      const result = await addContacts.mutateAsync({
        campaignId,
        contactIds: selectedContactIds,
      })
      toast(`Added ${result.added} contact${result.added !== 1 ? 's' : ''} to campaign`, 'success')
      onSelectionChange([])
    } catch {
      toast('Failed to add contacts to campaign', 'error')
    }
  }, [selectedContactIds, campaignId, addContacts, toast, onSelectionChange])

  // Remove selected contacts from campaign
  const handleRemoveFromCampaign = useCallback(async () => {
    if (selectedContactIds.length === 0) return
    try {
      const result = await removeContacts.mutateAsync({
        campaignId,
        contactIds: selectedContactIds,
      })
      toast(`Removed ${result.removed} contact${result.removed !== 1 ? 's' : ''} from campaign`, 'success')
      onSelectionChange([])
    } catch {
      toast('Failed to remove contacts from campaign', 'error')
    }
  }, [selectedContactIds, campaignId, removeContacts, toast, onSelectionChange])

  // Selection summary stats
  const selectionStats = useMemo(() => {
    const selected = sortedContacts.filter((c) => selectedSet.has(c.id))
    const withEmail = selected.filter((c) => !!c.email_address).length
    const withLinkedin = selected.filter((c) => !!c.linkedin_url).length
    const noEnrichment = selected.filter((c) => c.enrichment_level === 'None').length
    return { total: selectedSet.size, withEmail, withLinkedin, noEnrichment }
  }, [sortedContacts, selectedSet])

  // Filter bar config
  const filterConfigs: FilterConfig[] = useMemo(() => [
    { key: 'owner', label: 'Owner', type: 'select' as const, options: ownerOptions },
    { key: 'tag', label: 'Tag', type: 'select' as const, options: tagOptions },
    { key: 'industry', label: 'Industry', type: 'select' as const, options: industryOptions },
    { key: 'companyStatus', label: 'Status', type: 'select' as const, options: statusOptions },
    { key: 'search', label: 'Contacts', type: 'search' as const, placeholder: 'Search name, email, title...' },
  ], [ownerOptions, tagOptions, industryOptions, statusOptions])

  // Header checkbox state
  const allVisibleSelected = sortedContacts.length > 0 &&
    sortedContacts.every((c) => selectedSet.has(c.id))
  const someSelected = selectedSet.size > 0

  // Sort indicator
  const sortIcon = (field: SortField) => {
    if (sortField !== field) return null
    return (
      <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" className={sortDir === 'desc' ? 'rotate-180' : ''}>
        <path d="M6 3l3 4H3z" />
      </svg>
    )
  }

  // Presence dot
  const presenceDot = (present: boolean) => (
    <span
      className={`inline-block w-2 h-2 rounded-full ${present ? 'bg-success' : 'bg-[#8B92A0]/30'}`}
      title={present ? 'Available' : 'Missing'}
    />
  )

  // Loading state
  if (isLoading && !data) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-2 border-border border-t-accent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex flex-col min-h-0">
      {/* Filter bar + enrichment toggle */}
      <div className="flex flex-col gap-2 mb-3">
        <FilterBar
          filters={filterConfigs}
          values={{ owner, tag, industry, companyStatus, search }}
          onChange={handleFilterChange}
          total={totalCount}
          action={
            <label className="flex items-center gap-1.5 text-sm text-text-muted cursor-pointer whitespace-nowrap select-none ml-2">
              <input
                type="checkbox"
                checked={enrichmentReady}
                onChange={(e) => setEnrichmentReady(e.target.checked)}
                className="w-4 h-4 accent-accent cursor-pointer"
              />
              Enrichment ready
            </label>
          }
        />
      </div>

      {/* Selection summary */}
      {selectionStats.total > 0 && (
        <div className="flex flex-wrap items-center gap-3 text-xs text-text-muted mb-3 px-1">
          <span className="font-medium text-text">
            {selectionStats.total} contact{selectionStats.total !== 1 ? 's' : ''} selected
          </span>
          <span className="flex items-center gap-1">
            {presenceDot(true)} {selectionStats.withEmail} with email
          </span>
          <span className="flex items-center gap-1">
            {presenceDot(true)} {selectionStats.withLinkedin} with LinkedIn
          </span>
          {selectionStats.noEnrichment > 0 && (
            <span className="text-warning flex items-center gap-1">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M7 1L1 13h12L7 1z" />
                <path d="M7 5.5v3M7 10.5v.5" />
              </svg>
              {selectionStats.noEnrichment} contact{selectionStats.noEnrichment !== 1 ? 's' : ''} have no enrichment data
            </span>
          )}
        </div>
      )}

      {/* Table */}
      <div className="flex-1 min-h-0 overflow-auto border border-border-solid rounded-lg bg-surface" style={{ maxHeight: '60vh' }}>
        <table className="w-full text-sm border-collapse" style={{ minWidth: 700 }}>
          <thead className="sticky top-0 z-10 bg-surface-alt">
            <tr>
              {/* Checkbox header */}
              <th className="w-10 px-2 py-2.5 border-b border-border-solid text-center">
                <input
                  type="checkbox"
                  checked={allVisibleSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = someSelected && !allVisibleSelected
                  }}
                  onChange={toggleSelectAll}
                  aria-label="Select all"
                  className="cursor-pointer w-4 h-4 accent-accent"
                />
              </th>
              {/* Contact */}
              <HeaderCell field="name" label="Contact" onSort={handleSort} sortIcon={sortIcon} minWidth="180px" />
              {/* Company */}
              <HeaderCell field="company" label="Company" onSort={handleSort} sortIcon={sortIcon} minWidth="140px" />
              {/* Channels */}
              <th className="text-center text-xs font-medium text-text-muted px-2 py-2.5 border-b border-border-solid whitespace-nowrap" style={{ width: '80px' }}>
                Channels
              </th>
              {/* Enrichment */}
              <HeaderCell field="enrichment" label="Enrichment" onSort={handleSort} sortIcon={sortIcon} width="90px" />
              {/* Score */}
              <HeaderCell field="score" label="Score" onSort={handleSort} sortIcon={sortIcon} width="70px" />
            </tr>
          </thead>
          <tbody>
            {sortedContacts.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-12 text-center text-text-dim text-sm">
                  {isLoading ? 'Loading contacts...' : 'No contacts match your filters.'}
                </td>
              </tr>
            ) : (
              sortedContacts.map((contact) => (
                <ContactRow
                  key={contact.id}
                  contact={contact}
                  isSelected={selectedSet.has(contact.id)}
                  onToggle={toggleSelect}
                />
              ))
            )}
          </tbody>
        </table>

        {/* Infinite scroll sentinel */}
        <div ref={sentinelRef} className="h-1" />

        {/* Loading indicator for next page */}
        {isFetchingNextPage && (
          <div className="flex items-center justify-center py-3">
            <div className="w-5 h-5 border-2 border-border border-t-accent rounded-full animate-spin" />
            <span className="ml-2 text-sm text-text-muted">Loading more...</span>
          </div>
        )}
      </div>

      {/* Loaded / total indicator */}
      {sortedContacts.length > 0 && (
        <div className="text-xs text-text-dim mt-2 text-right">
          Showing {sortedContacts.length} of {totalCount.toLocaleString()} contacts
        </div>
      )}

      {/* Bulk action bar */}
      <SelectionActionBar
        count={selectedSet.size}
        actions={[
          {
            label: 'Add to Campaign',
            icon: (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M7 3v8M3 7h8" />
              </svg>
            ),
            onClick: handleAddToCampaign,
            loading: addContacts.isPending,
          },
          {
            label: 'Remove',
            icon: (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 7h8" />
              </svg>
            ),
            onClick: handleRemoveFromCampaign,
            loading: removeContacts.isPending,
          },
        ]}
        onDeselectAll={() => onSelectionChange([])}
      />
    </div>
  )
}

// ── Sub-components ──────────────────────────────────────

function HeaderCell({
  field,
  label,
  onSort,
  sortIcon,
  minWidth,
  width,
}: {
  field: SortField
  label: string
  onSort: (f: SortField) => void
  sortIcon: (f: SortField) => React.ReactNode
  minWidth?: string
  width?: string
}) {
  return (
    <th
      onClick={() => onSort(field)}
      className="text-left text-xs font-medium text-text-muted px-3 py-2.5 border-b border-border-solid whitespace-nowrap cursor-pointer hover:text-text select-none"
      style={{ minWidth, width }}
    >
      <span className="flex items-center gap-1">
        {label} {sortIcon(field)}
      </span>
    </th>
  )
}

function ContactRow({
  contact,
  isSelected,
  onToggle,
}: {
  contact: PickerContact
  isSelected: boolean
  onToggle: (id: string) => void
}) {
  const badge = ENRICHMENT_BADGE[contact.enrichment_level]
  const hasEmail = !!contact.email_address
  const hasLinkedin = !!contact.linkedin_url

  return (
    <tr
      className={`border-b border-border/30 ${isSelected ? 'bg-accent/5' : ''} hover:bg-surface-alt/30 cursor-pointer`}
      onClick={() => onToggle(contact.id)}
    >
      {/* Checkbox */}
      <td className="w-10 px-2 py-2.5 text-center">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => onToggle(contact.id)}
          onClick={(e) => e.stopPropagation()}
          aria-label={`Select ${contact.full_name}`}
          className="cursor-pointer w-4 h-4 accent-accent"
        />
      </td>

      {/* Contact name + job title */}
      <td className="px-3 py-2.5">
        <div className="flex flex-col min-w-0">
          <span className="text-sm text-text truncate">{contact.full_name}</span>
          {contact.job_title && (
            <span className="text-xs text-text-dim truncate">{contact.job_title}</span>
          )}
        </div>
      </td>

      {/* Company */}
      <td className="px-3 py-2.5">
        <div className="flex flex-col min-w-0">
          <span className="text-sm text-text-muted truncate">
            {contact.company_name ?? '--'}
          </span>
        </div>
      </td>

      {/* Channel indicators */}
      <td className="px-2 py-2.5 text-center">
        <div className="flex items-center justify-center gap-2">
          <span
            className={`inline-block w-2.5 h-2.5 rounded-full ${hasEmail ? 'bg-success' : 'bg-[#8B92A0]/30'}`}
            title={hasEmail ? `Email: ${contact.email_address}` : 'No email'}
          />
          <span
            className={`inline-block w-2.5 h-2.5 rounded-full ${hasLinkedin ? 'bg-accent' : 'bg-[#8B92A0]/30'}`}
            title={hasLinkedin ? 'LinkedIn available' : 'No LinkedIn'}
          />
        </div>
      </td>

      {/* Enrichment badge */}
      <td className="px-3 py-2.5">
        <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border whitespace-nowrap ${badge.classes}`}>
          {badge.label}
        </span>
      </td>

      {/* Score */}
      <td className="px-3 py-2.5 text-center text-sm text-text-muted">
        {contact.contact_score ?? '--'}
      </td>
    </tr>
  )
}
