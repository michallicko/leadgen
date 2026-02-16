import { useState, useMemo, useCallback } from 'react'
import { useSearchParams, useParams } from 'react-router'
import { useContacts, type ContactListItem, type ContactFilters } from '../../api/queries/useContacts'
import { useBatches } from '../../api/queries/useBatches'
import { useLocalStorage } from '../../hooks/useLocalStorage'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { FilterBar, type FilterConfig } from '../../components/ui/FilterBar'
import { Badge } from '../../components/ui/Badge'
import { ContactDetail } from './ContactDetail'
import { DetailModal } from '../../components/ui/DetailModal'
import { useContact } from '../../api/queries/useContacts'
import {
  ICP_FIT_DISPLAY,
  MESSAGE_STATUS_DISPLAY,
  filterOptions,
} from '../../lib/display'

export function ContactsPage() {
  const { namespace } = useParams<{ namespace: string }>()
  const [searchParams, setSearchParams] = useSearchParams()

  const [search, setSearch] = useLocalStorage('ct_filter_search', '')
  const [batchName, setBatchName] = useLocalStorage('ct_filter_batch', '')
  const [ownerName, setOwnerName] = useLocalStorage('ct_filter_owner', '')
  const [icpFit, setIcpFit] = useLocalStorage('ct_filter_icp', '')
  const [msgStatus, setMsgStatus] = useLocalStorage('ct_filter_msg_status', '')
  const [sortField, setSortField] = useLocalStorage('ct_sort_field', 'last_name')
  const [sortDir, setSortDir] = useLocalStorage<'asc' | 'desc'>('ct_sort_dir', 'asc')

  const openId = searchParams.get('open')
  const [selectedId, setSelectedId] = useState<string | null>(openId)

  const handleOpenDetail = useCallback((id: string | null) => {
    setSelectedId(id)
    if (id) {
      setSearchParams({ open: id }, { replace: true })
    } else {
      searchParams.delete('open')
      setSearchParams(searchParams, { replace: true })
    }
  }, [searchParams, setSearchParams])

  const { data: batchesData } = useBatches()

  const filters: ContactFilters = useMemo(() => ({
    search,
    batch_name: batchName,
    owner_name: ownerName,
    icp_fit: icpFit,
    message_status: msgStatus,
    sort: sortField,
    sort_dir: sortDir,
  }), [search, batchName, ownerName, icpFit, msgStatus, sortField, sortDir])

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

  const { data: contactDetail, isLoading: isDetailLoading } = useContact(selectedId)

  const handleFilterChange = useCallback((key: string, value: string) => {
    switch (key) {
      case 'search': setSearch(value); break
      case 'batch_name': setBatchName(value); break
      case 'owner_name': setOwnerName(value); break
      case 'icp_fit': setIcpFit(value); break
      case 'message_status': setMsgStatus(value); break
    }
  }, [setSearch, setBatchName, setOwnerName, setIcpFit, setMsgStatus])

  const handleSort = useCallback((field: string, dir: 'asc' | 'desc') => {
    setSortField(field)
    setSortDir(dir)
  }, [setSortField, setSortDir])

  const filterConfigs: FilterConfig[] = useMemo(() => [
    { key: 'search', label: 'contacts', type: 'search' as const, placeholder: 'Search name, email, title...' },
    { key: 'batch_name', label: 'Batch', type: 'select' as const, options: (batchesData?.batches ?? []).map((b) => ({ value: b.name, label: b.name })) },
    { key: 'owner_name', label: 'Owner', type: 'select' as const, options: (batchesData?.owners ?? []).map((o) => ({ value: o.name, label: o.name })) },
    { key: 'icp_fit', label: 'ICP Fit', type: 'select' as const, options: filterOptions(ICP_FIT_DISPLAY) },
    { key: 'message_status', label: 'Msg Status', type: 'select' as const, options: filterOptions(MESSAGE_STATUS_DISPLAY) },
  ], [batchesData])

  const columns: Column<ContactListItem>[] = useMemo(() => [
    { key: 'full_name', label: 'Name', sortKey: 'last_name', width: '16%' },
    { key: 'job_title', label: 'Title', sortKey: 'job_title', width: '14%' },
    { key: 'company_name', label: 'Company', width: '13%' },
    { key: 'email_address', label: 'Email', sortKey: 'email_address', width: '16%', render: (c) => c.email_address ? (
      <a href={`mailto:${c.email_address}`} onClick={(e) => e.stopPropagation()} className="text-accent-cyan hover:underline truncate block">{c.email_address}</a>
    ) : '-' },
    { key: 'contact_score', label: 'Score', sortKey: 'contact_score', width: '7%' },
    { key: 'icp_fit', label: 'ICP Fit', sortKey: 'icp_fit', width: '10%', render: (c) => <Badge variant="icp" value={c.icp_fit} /> },
    { key: 'message_status', label: 'Msg Status', sortKey: 'message_status', width: '10%', render: (c) => <Badge variant="msgStatus" value={c.message_status} /> },
    { key: 'owner_name', label: 'Owner', width: '7%' },
    { key: 'batch_name', label: 'Batch', width: '7%' },
  ], [])

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      <FilterBar
        filters={filterConfigs}
        values={{ search, batch_name: batchName, owner_name: ownerName, icp_fit: icpFit, message_status: msgStatus }}
        onChange={handleFilterChange}
        total={total}
      />

      <DataTable
        columns={columns}
        data={allContacts}
        sort={{ field: sortField, dir: sortDir }}
        onSort={handleSort}
        onRowClick={(c) => handleOpenDetail(c.id)}
        onLoadMore={() => fetchNextPage()}
        hasMore={hasNextPage}
        isLoading={isLoading || isFetchingNextPage}
        emptyText="No contacts match your filters."
      />

      <DetailModal
        isOpen={!!selectedId}
        onClose={() => handleOpenDetail(null)}
        title={contactDetail?.full_name ?? 'Contact'}
        subtitle={contactDetail?.job_title ?? undefined}
        isLoading={isDetailLoading}
      >
        {contactDetail && (
          <ContactDetail
            contact={contactDetail}
            namespace={namespace}
            onClose={() => handleOpenDetail(null)}
          />
        )}
      </DetailModal>
    </div>
  )
}
