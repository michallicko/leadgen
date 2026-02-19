import { useState, useMemo, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router'
import { withRev } from '../../lib/revision'
import { useContacts, type ContactListItem, type ContactFilters } from '../../api/queries/useContacts'
import { useTags } from '../../api/queries/useTags'
import { useBulkAddTags, useBulkAssignCampaign, useContactsMatchingCount } from '../../api/queries/useBulkActions'
import { useLocalStorage } from '../../hooks/useLocalStorage'
import { DataTable, type Column, type SelectionMode } from '../../components/ui/DataTable'
import { FilterBar, type FilterConfig } from '../../components/ui/FilterBar'
import { SelectionActionBar } from '../../components/ui/SelectionActionBar'
import { TagPicker } from '../../components/ui/TagPicker'
import { CampaignPicker } from '../../components/ui/CampaignPicker'
import { Badge } from '../../components/ui/Badge'
import { useToast } from '../../components/ui/Toast'
import {
  ICP_FIT_DISPLAY,
  MESSAGE_STATUS_DISPLAY,
  filterOptions,
} from '../../lib/display'

export function ContactsPage() {
  const { namespace } = useParams<{ namespace: string }>()
  const navigate = useNavigate()
  const { toast } = useToast()

  const [search, setSearch] = useLocalStorage('ct_filter_search', '')
  const [tagName, setTagName] = useLocalStorage('ct_filter_tag', '')
  const [ownerName, setOwnerName] = useLocalStorage('ct_filter_owner', '')
  const [icpFit, setIcpFit] = useLocalStorage('ct_filter_icp', '')
  const [msgStatus, setMsgStatus] = useLocalStorage('ct_filter_msg_status', '')
  const [sortField, setSortField] = useLocalStorage('ct_sort_field', 'last_name')
  const [sortDir, setSortDir] = useLocalStorage<'asc' | 'desc'>('ct_sort_dir', 'asc')

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [selectionMode, setSelectionMode] = useState<SelectionMode>('explicit')
  const [showTagPicker, setShowTagPicker] = useState(false)
  const [showCampaignPicker, setShowCampaignPicker] = useState(false)

  const { data: tagsData } = useTags()
  const bulkAddTags = useBulkAddTags()
  const bulkAssignCampaign = useBulkAssignCampaign()
  const matchingCount = useContactsMatchingCount()

  const filters: ContactFilters = useMemo(() => ({
    search,
    tag_name: tagName,
    owner_name: ownerName,
    icp_fit: icpFit,
    message_status: msgStatus,
    sort: sortField,
    sort_dir: sortDir,
  }), [search, tagName, ownerName, icpFit, msgStatus, sortField, sortDir])

  const activeFilters = useMemo(() => {
    const f: Record<string, string> = {}
    if (search) f.search = search
    if (tagName) f.tag_name = tagName
    if (ownerName) f.owner_name = ownerName
    if (icpFit) f.icp_fit = icpFit
    if (msgStatus) f.message_status = msgStatus
    return f
  }, [search, tagName, ownerName, icpFit, msgStatus])

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
    switch (key) {
      case 'search': setSearch(value); break
      case 'tag_name': setTagName(value); break
      case 'owner_name': setOwnerName(value); break
      case 'icp_fit': setIcpFit(value); break
      case 'message_status': setMsgStatus(value); break
    }
    // Clear selection when filters change
    setSelectedIds(new Set())
    setSelectionMode('explicit')
  }, [setSearch, setTagName, setOwnerName, setIcpFit, setMsgStatus])

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

  return (
    <div className="flex flex-col h-full min-h-0">
      <FilterBar
        filters={filterConfigs}
        values={{ search, tag_name: tagName, owner_name: ownerName, icp_fit: icpFit, message_status: msgStatus }}
        onChange={handleFilterChange}
        total={total}
      />

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
