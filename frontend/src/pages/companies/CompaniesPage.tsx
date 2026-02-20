import { useState, useMemo, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router'
import { withRev } from '../../lib/revision'
import { useCompanies, type CompanyFilters } from '../../api/queries/useCompanies'
import { useTags } from '../../api/queries/useTags'
import { useBulkAddTags, useCompaniesMatchingCount } from '../../api/queries/useBulkActions'
import { useLocalStorage } from '../../hooks/useLocalStorage'
import { useColumnVisibility } from '../../hooks/useColumnVisibility'
import { DataTable, type SelectionMode } from '../../components/ui/DataTable'
import { FilterBar, type FilterConfig } from '../../components/ui/FilterBar'
import { ColumnPicker } from '../../components/ui/ColumnPicker'
import { SelectionActionBar } from '../../components/ui/SelectionActionBar'
import { TagPicker } from '../../components/ui/TagPicker'
import { useToast } from '../../components/ui/Toast'
import { COMPANY_COLUMNS, COMPANY_ALWAYS_VISIBLE } from '../../config/companyColumns'
import {
  STATUS_DISPLAY,
  TIER_DISPLAY,
  filterOptions,
} from '../../lib/display'

export function CompaniesPage() {
  const { namespace } = useParams<{ namespace: string }>()
  const navigate = useNavigate()
  const { toast } = useToast()

  // Filters persisted in localStorage
  const [search, setSearch] = useLocalStorage('co_filter_search', '')
  const [status, setStatus] = useLocalStorage('co_filter_status', '')
  const [tier, setTier] = useLocalStorage('co_filter_tier', '')
  const [tagName, setTagName] = useLocalStorage('co_filter_tag', '')
  const [ownerName, setOwnerName] = useLocalStorage('co_filter_owner', '')
  const [sortField, setSortField] = useLocalStorage('co_sort_field', 'name')
  const [sortDir, setSortDir] = useLocalStorage<'asc' | 'desc'>('co_sort_dir', 'asc')

  // Column visibility
  const [visibleKeys, setVisibleKeys, resetColumns] = useColumnVisibility(
    'co_visible_cols',
    COMPANY_COLUMNS,
  )

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [selectionMode, setSelectionMode] = useState<SelectionMode>('explicit')
  const [showTagPicker, setShowTagPicker] = useState(false)

  const { data: tagsData } = useTags()
  const bulkAddTags = useBulkAddTags()
  const matchingCount = useCompaniesMatchingCount()

  const filters: CompanyFilters = useMemo(() => ({
    search,
    status,
    tier,
    tag_name: tagName,
    owner_name: ownerName,
    sort: sortField,
    sort_dir: sortDir,
  }), [search, status, tier, tagName, ownerName, sortField, sortDir])

  const activeFilters = useMemo(() => {
    const f: Record<string, string> = {}
    if (search) f.search = search
    if (status) f.status = status
    if (tier) f.tier = tier
    if (tagName) f.tag_name = tagName
    if (ownerName) f.owner_name = ownerName
    return f
  }, [search, status, tier, tagName, ownerName])

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
  } = useCompanies(filters)

  const allCompanies = useMemo(
    () => data?.pages.flatMap((p) => p.companies) ?? [],
    [data],
  )
  const total = data?.pages[0]?.total ?? 0

  const handleFilterChange = useCallback((key: string, value: string) => {
    switch (key) {
      case 'search': setSearch(value); break
      case 'status': setStatus(value); break
      case 'tier': setTier(value); break
      case 'tag_name': setTagName(value); break
      case 'owner_name': setOwnerName(value); break
    }
    // Clear selection when filters change
    setSelectedIds(new Set())
    setSelectionMode('explicit')
  }, [setSearch, setStatus, setTier, setTagName, setOwnerName])

  const handleSort = useCallback((field: string, dir: 'asc' | 'desc') => {
    setSortField(field)
    setSortDir(dir)
  }, [setSortField, setSortDir])

  const handleSelectionChange = useCallback((ids: Set<string>, mode: SelectionMode) => {
    setSelectedIds(ids)
    setSelectionMode(mode)
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
        ? { entity_type: 'company' as const, filters: activeFilters, tag_ids: tagIds }
        : { entity_type: 'company' as const, ids: Array.from(selectedIds), tag_ids: tagIds }
      const result = await bulkAddTags.mutateAsync(payload)
      toast(`Tagged ${result.affected} compan${result.affected !== 1 ? 'ies' : 'y'} (${result.new_assignments} new)`, 'success')
      setShowTagPicker(false)
      handleDeselectAll()
    } catch {
      toast('Failed to add tags', 'error')
    }
  }, [selectionMode, activeFilters, selectedIds, bulkAddTags, toast, handleDeselectAll])

  const selectionCount = selectionMode === 'all-matching'
    ? (matchingCount.data?.count ?? total)
    : selectedIds.size

  const filterConfigs: FilterConfig[] = useMemo(() => [
    { key: 'search', label: 'companies', type: 'search' as const, placeholder: 'Search name or domain...' },
    { key: 'status', label: 'Status', type: 'select' as const, options: filterOptions(STATUS_DISPLAY) },
    { key: 'tier', label: 'Tier', type: 'select' as const, options: filterOptions(TIER_DISPLAY) },
    { key: 'tag_name', label: 'Tag', type: 'select' as const, options: (tagsData?.tags ?? []).map((b) => ({ value: b.name, label: b.name })) },
    { key: 'owner_name', label: 'Owner', type: 'select' as const, options: (tagsData?.owners ?? []).map((o) => ({ value: o.name, label: o.name })) },
  ], [tagsData])

  // Filter columns by visibility
  const visibleSet = new Set(visibleKeys)
  const columns = useMemo(
    () => COMPANY_COLUMNS.filter((c) => visibleSet.has(c.key)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [visibleKeys],
  )

  return (
    <div className="flex flex-col h-full min-h-0">
      <FilterBar
        filters={filterConfigs}
        values={{ search, status, tier, tag_name: tagName, owner_name: ownerName }}
        onChange={handleFilterChange}
        total={total}
        action={
          <div className="flex items-center gap-2">
            {namespace && (
              <a
                href={`/${namespace}/enrich`}
                className="text-xs text-accent-cyan hover:underline"
              >
                Enrich Selection
              </a>
            )}
            <ColumnPicker
              allColumns={COMPANY_COLUMNS}
              visibleKeys={visibleKeys}
              onChange={setVisibleKeys}
              onReset={resetColumns}
              alwaysVisible={COMPANY_ALWAYS_VISIBLE}
            />
          </div>
        }
      />

      <DataTable
        columns={columns}
        data={allCompanies}
        sort={{ field: sortField, dir: sortDir }}
        onSort={handleSort}
        onRowClick={(c) => navigate(withRev(`/${namespace}/companies/${c.id}`), { state: { origin: withRev(`/${namespace}/companies`) } })}
        onLoadMore={() => fetchNextPage()}
        hasMore={hasNextPage}
        isLoading={isLoading || isFetchingNextPage}
        emptyText="No companies match your filters."
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
    </div>
  )
}
