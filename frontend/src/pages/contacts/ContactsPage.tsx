import { useState, useMemo, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router'
import { withRev } from '../../lib/revision'
import { useContacts, type ContactListItem, type ContactFilters } from '../../api/queries/useContacts'
import { useTags } from '../../api/queries/useTags'
import { useBulkAddTags, useBulkAssignCampaign, useContactsMatchingCount } from '../../api/queries/useBulkActions'
import { useLocalStorage } from '../../hooks/useLocalStorage'
import { useAdvancedFilters } from '../../hooks/useAdvancedFilters'
import { useFilterCounts } from '../../hooks/useFilterCounts'
import { DataTable, type Column, type SelectionMode } from '../../components/ui/DataTable'
import { FilterBar, type FilterConfig } from '../../components/ui/FilterBar'
import { MultiSelectFilter } from '../../components/ui/MultiSelectFilter'
import { JobTitleFilter } from '../../components/ui/JobTitleFilter'
import { SelectionActionBar } from '../../components/ui/SelectionActionBar'
import { TagPicker } from '../../components/ui/TagPicker'
import { CampaignPicker } from '../../components/ui/CampaignPicker'
import { Badge } from '../../components/ui/Badge'
import { useToast } from '../../components/ui/Toast'
import {
  ICP_FIT_DISPLAY,
  MESSAGE_STATUS_DISPLAY,
  INDUSTRY_DISPLAY,
  COMPANY_SIZE_DISPLAY,
  GEO_REGION_DISPLAY,
  REVENUE_RANGE_DISPLAY,
  SENIORITY_DISPLAY,
  DEPARTMENT_DISPLAY,
  LINKEDIN_ACTIVITY_DISPLAY,
  filterOptions,
} from '../../lib/display'

/** Build MultiSelectFilter options from a display map + optional facet counts */
function buildMultiOptions(
  displayMap: Record<string, string>,
  facets?: { value: string; count: number }[],
) {
  const countMap = new Map<string, number>()
  if (facets) {
    for (const f of facets) countMap.set(f.value, f.count)
  }
  return Object.entries(displayMap).map(([dbVal, label]) => ({
    value: dbVal,
    label,
    count: countMap.get(dbVal),
  }))
}

export function ContactsPage() {
  const { namespace } = useParams<{ namespace: string }>()
  const navigate = useNavigate()
  const { toast } = useToast()

  // Advanced filters (persisted to localStorage)
  const {
    filters: advFilters,
    setSimpleFilter,
    setMultiFilter,
    toggleExclude,
    clearAll,
    activeFilterCount,
    toQueryParams,
    toCountsPayload,
  } = useAdvancedFilters('ct_adv_filters')

  const [sortField, setSortField] = useLocalStorage('ct_sort_field', 'last_name')
  const [sortDir, setSortDir] = useLocalStorage<'asc' | 'desc'>('ct_sort_dir', 'asc')
  const [showAdvanced, setShowAdvanced] = useLocalStorage('ct_show_advanced', false)

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [selectionMode, setSelectionMode] = useState<SelectionMode>('explicit')
  const [showTagPicker, setShowTagPicker] = useState(false)
  const [showCampaignPicker, setShowCampaignPicker] = useState(false)

  const { data: tagsData } = useTags()
  const bulkAddTags = useBulkAddTags()
  const bulkAssignCampaign = useBulkAssignCampaign()
  const matchingCount = useContactsMatchingCount()

  // Build ContactFilters from advanced state + sort
  const filters: ContactFilters = useMemo(() => ({
    ...toQueryParams(),
    sort: sortField,
    sort_dir: sortDir,
  }), [toQueryParams, sortField, sortDir])

  // Active filters for bulk actions (simple key-value pairs for existing API)
  const activeFilters = useMemo(() => {
    const params = toQueryParams()
    // Remove sort params — bulk actions don't need them
    delete params.sort
    delete params.sort_dir
    return params
  }, [toQueryParams])

  // Filter counts for faceted options
  const countsPayload = useMemo(() => toCountsPayload(), [toCountsPayload])
  const { data: countsData } = useFilterCounts(countsPayload)

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
  } = useContacts(filters)

  const allContacts = useMemo(
    () => data?.pages.flatMap((p) => p.contacts) ?? [],
    [data],
  )
  const total = data?.pages[0]?.total ?? 0

  const handleFilterChange = useCallback((key: string, value: string) => {
    setSimpleFilter(key, value)
    // Clear selection when filters change
    setSelectedIds(new Set())
    setSelectionMode('explicit')
  }, [setSimpleFilter])

  const handleSort = useCallback((field: string, dir: 'asc' | 'desc') => {
    setSortField(field)
    setSortDir(dir)
  }, [setSortField, setSortDir])

  const handleSelectionChange = useCallback((ids: Set<string>, mode: SelectionMode) => {
    setSelectedIds(ids)
    setSelectionMode(mode)
    // Fetch matching count when switching to all-matching
    if (mode === 'all-matching') {
      matchingCount.mutate(activeFilters)
    }
  }, [matchingCount, activeFilters])

  const handleDeselectAll = useCallback(() => {
    setSelectedIds(new Set())
    setSelectionMode('explicit')
  }, [])

  const handleAddTags = useCallback(async (tagIds: string[]) => {
    try {
      const payload = selectionMode === 'all-matching'
        ? { entity_type: 'contact' as const, filters: activeFilters, tag_ids: tagIds }
        : { entity_type: 'contact' as const, ids: Array.from(selectedIds), tag_ids: tagIds }
      const result = await bulkAddTags.mutateAsync(payload)
      toast(`Tagged ${result.affected} contact${result.affected !== 1 ? 's' : ''} (${result.new_assignments} new)`, 'success')
      setShowTagPicker(false)
      handleDeselectAll()
    } catch {
      toast('Failed to add tags', 'error')
    }
  }, [selectionMode, activeFilters, selectedIds, bulkAddTags, toast, handleDeselectAll])

  const handleAssignCampaign = useCallback(async (campaignId: string) => {
    try {
      const payload = selectionMode === 'all-matching'
        ? { entity_type: 'contact' as const, filters: activeFilters, campaign_id: campaignId }
        : { entity_type: 'contact' as const, ids: Array.from(selectedIds), campaign_id: campaignId }
      const result = await bulkAssignCampaign.mutateAsync(payload)
      toast(`Assigned ${result.affected} contact${result.affected !== 1 ? 's' : ''} to campaign`, 'success')
      setShowCampaignPicker(false)
      handleDeselectAll()
    } catch {
      toast('Failed to assign to campaign', 'error')
    }
  }, [selectionMode, activeFilters, selectedIds, bulkAssignCampaign, toast, handleDeselectAll])

  const selectionCount = selectionMode === 'all-matching'
    ? (matchingCount.data?.count ?? total)
    : selectedIds.size

  const filterConfigs: FilterConfig[] = useMemo(() => [
    { key: 'search', label: 'contacts', type: 'search' as const, placeholder: 'Search name, email, title...' },
    { key: 'tag_name', label: 'Tag', type: 'select' as const, options: (tagsData?.tags ?? []).map((b) => ({ value: b.name, label: b.name })) },
    { key: 'owner_name', label: 'Owner', type: 'select' as const, options: (tagsData?.owners ?? []).map((o) => ({ value: o.name, label: o.name })) },
    { key: 'icp_fit', label: 'ICP Fit', type: 'select' as const, options: filterOptions(ICP_FIT_DISPLAY) },
    { key: 'message_status', label: 'Msg Status', type: 'select' as const, options: filterOptions(MESSAGE_STATUS_DISPLAY) },
  ], [tagsData])

  const columns: Column<ContactListItem>[] = useMemo(() => [
    { key: 'full_name', label: 'Name', sortKey: 'last_name', minWidth: '130px' },
    { key: 'job_title', label: 'Title', sortKey: 'job_title', minWidth: '120px' },
    { key: 'company_name', label: 'Company', minWidth: '120px' },
    { key: 'email_address', label: 'Email', sortKey: 'email_address', minWidth: '140px', render: (c) => c.email_address ? (
      <a href={`mailto:${c.email_address}`} onClick={(e) => e.stopPropagation()} className="text-accent-cyan hover:underline truncate block">{c.email_address}</a>
    ) : '-' },
    { key: 'contact_score', label: 'Score', sortKey: 'contact_score', minWidth: '55px' },
    { key: 'icp_fit', label: 'ICP Fit', sortKey: 'icp_fit', minWidth: '100px', shrink: false, render: (c) => <Badge variant="icp" value={c.icp_fit} /> },
    { key: 'message_status', label: 'Msg Status', sortKey: 'message_status', minWidth: '100px', shrink: false, render: (c) => <Badge variant="msgStatus" value={c.message_status} /> },
    { key: 'owner_name', label: 'Owner', minWidth: '70px' },
    { key: 'tag_names', label: 'Tags', minWidth: '90px', render: (c) => {
      const names = (c as unknown as Record<string, unknown>).tag_names as string[] | undefined
      if (!names || names.length === 0) return <span className="text-text-dim">-</span>
      return <span className="text-xs" title={names.join(', ')}>{names.join(', ')}</span>
    }},
  ], [])

  const facets = countsData?.facets

  return (
    <div className="flex flex-col h-full min-h-0">
      <FilterBar
        filters={filterConfigs}
        values={{
          search: advFilters.search,
          tag_name: advFilters.tag_name,
          owner_name: advFilters.owner_name,
          icp_fit: advFilters.icp_fit,
          message_status: advFilters.message_status,
        }}
        onChange={handleFilterChange}
        total={total}
        action={
          <button
            type="button"
            className="px-2.5 py-1.5 text-xs rounded-md border border-border-solid bg-surface-alt text-text-muted hover:text-text hover:border-accent transition-colors flex items-center gap-1.5"
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M1.5 3.5h11M3.5 7h7M5.5 10.5h3" />
            </svg>
            ICP Filters
            {activeFilterCount > 0 && (
              <span className="inline-flex items-center justify-center w-4 h-4 text-[10px] font-bold rounded-full bg-accent-cyan text-bg">
                {activeFilterCount}
              </span>
            )}
          </button>
        }
      />

      {/* Advanced ICP filter row */}
      {showAdvanced && (
        <div className="flex flex-wrap items-center gap-2 mb-3 px-0.5">
          <MultiSelectFilter
            label="Industry"
            options={buildMultiOptions(INDUSTRY_DISPLAY, facets?.industry)}
            selected={advFilters.industry.values}
            exclude={advFilters.industry.exclude}
            onSelectionChange={(v) => setMultiFilter('industry', v)}
            onExcludeToggle={() => toggleExclude('industry')}
          />
          <MultiSelectFilter
            label="Company Size"
            options={buildMultiOptions(COMPANY_SIZE_DISPLAY, facets?.company_size)}
            selected={advFilters.company_size.values}
            exclude={advFilters.company_size.exclude}
            onSelectionChange={(v) => setMultiFilter('company_size', v)}
            onExcludeToggle={() => toggleExclude('company_size')}
          />
          <MultiSelectFilter
            label="Region"
            options={buildMultiOptions(GEO_REGION_DISPLAY, facets?.geo_region)}
            selected={advFilters.geo_region.values}
            exclude={advFilters.geo_region.exclude}
            onSelectionChange={(v) => setMultiFilter('geo_region', v)}
            onExcludeToggle={() => toggleExclude('geo_region')}
          />
          <MultiSelectFilter
            label="Revenue"
            options={buildMultiOptions(REVENUE_RANGE_DISPLAY, facets?.revenue_range)}
            selected={advFilters.revenue_range.values}
            exclude={advFilters.revenue_range.exclude}
            onSelectionChange={(v) => setMultiFilter('revenue_range', v)}
            onExcludeToggle={() => toggleExclude('revenue_range')}
          />
          <MultiSelectFilter
            label="Seniority"
            options={buildMultiOptions(SENIORITY_DISPLAY, facets?.seniority_level)}
            selected={advFilters.seniority_level.values}
            exclude={advFilters.seniority_level.exclude}
            onSelectionChange={(v) => setMultiFilter('seniority_level', v)}
            onExcludeToggle={() => toggleExclude('seniority_level')}
          />
          <MultiSelectFilter
            label="Department"
            options={buildMultiOptions(DEPARTMENT_DISPLAY, facets?.department)}
            selected={advFilters.department.values}
            exclude={advFilters.department.exclude}
            onSelectionChange={(v) => setMultiFilter('department', v)}
            onExcludeToggle={() => toggleExclude('department')}
          />
          <JobTitleFilter
            selected={advFilters.job_titles.values}
            exclude={advFilters.job_titles.exclude}
            onSelectionChange={(v) => setMultiFilter('job_titles', v)}
            onExcludeToggle={() => toggleExclude('job_titles')}
          />
          <MultiSelectFilter
            label="LinkedIn"
            options={buildMultiOptions(LINKEDIN_ACTIVITY_DISPLAY, facets?.linkedin_activity)}
            selected={advFilters.linkedin_activity.values}
            exclude={advFilters.linkedin_activity.exclude}
            onSelectionChange={(v) => setMultiFilter('linkedin_activity', v)}
            onExcludeToggle={() => toggleExclude('linkedin_activity')}
            searchable={false}
          />
          {activeFilterCount > 0 && (
            <button
              type="button"
              className="px-2 py-1 text-xs text-text-muted hover:text-error transition-colors"
              onClick={() => { clearAll(); setSelectedIds(new Set()); setSelectionMode('explicit') }}
            >
              Clear all
            </button>
          )}
        </div>
      )}

      <DataTable
        columns={columns}
        data={allContacts}
        sort={{ field: sortField, dir: sortDir }}
        onSort={handleSort}
        onRowClick={selectedIds.size === 0 ? (c) => navigate(withRev(`/${namespace}/contacts/${c.id}`), { state: { origin: withRev(`/${namespace}/contacts`) } }) : undefined}
        onLoadMore={() => fetchNextPage()}
        hasMore={hasNextPage}
        isLoading={isLoading || isFetchingNextPage}
        emptyText="No contacts match your filters."
        selectable
        selectedIds={selectedIds}
        onSelectionChange={handleSelectionChange}
        totalMatching={total}
      />

      <SelectionActionBar
        count={selectionCount}
        isAllMatching={selectionMode === 'all-matching'}
        totalMatching={selectionMode === 'all-matching' ? (matchingCount.data?.count ?? total) : undefined}
        actions={[
          {
            label: 'Add Tags',
            icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M7.5 1.5h4a1 1 0 0 1 1 1v4L6.5 12.5l-5-5L7.5 1.5z" /><circle cx="10" cy="4" r="0.5" fill="currentColor" /></svg>,
            onClick: () => setShowTagPicker(true),
            loading: bulkAddTags.isPending,
          },
          {
            label: 'Assign Campaign',
            icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 3.5h10M2 7h10M2 10.5h6" /></svg>,
            onClick: () => setShowCampaignPicker(true),
            loading: bulkAssignCampaign.isPending,
          },
        ]}
        onDeselectAll={handleDeselectAll}
      />

      {showTagPicker && (
        <TagPicker
          onConfirm={handleAddTags}
          onClose={() => setShowTagPicker(false)}
          isLoading={bulkAddTags.isPending}
        />
      )}

      {showCampaignPicker && (
        <CampaignPicker
          onConfirm={handleAssignCampaign}
          onClose={() => setShowCampaignPicker(false)}
          isLoading={bulkAssignCampaign.isPending}
        />
      )}
    </div>
  )
}
