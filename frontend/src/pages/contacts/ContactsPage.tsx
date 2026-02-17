import { useMemo, useCallback } from 'react'
import { useContacts, useContact, type ContactListItem, type ContactFilters } from '../../api/queries/useContacts'
import { useCompany } from '../../api/queries/useCompanies'
import { useTags } from '../../api/queries/useTags'
import { useLocalStorage } from '../../hooks/useLocalStorage'
import { useEntityStack } from '../../hooks/useEntityStack'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { FilterBar, type FilterConfig } from '../../components/ui/FilterBar'
import { Badge } from '../../components/ui/Badge'
import { ContactDetail } from './ContactDetail'
import { CompanyDetail } from '../companies/CompanyDetail'
import { DetailModal } from '../../components/ui/DetailModal'
import {
  ICP_FIT_DISPLAY,
  MESSAGE_STATUS_DISPLAY,
  filterOptions,
} from '../../lib/display'

export function ContactsPage() {
  // namespace extracted from URL by useEntityStack

  // Entity stack for cross-entity modal navigation
  const stack = useEntityStack('contact')

  const [search, setSearch] = useLocalStorage('ct_filter_search', '')
  const [tagName, setTagName] = useLocalStorage('ct_filter_tag', '')
  const [ownerName, setOwnerName] = useLocalStorage('ct_filter_owner', '')
  const [icpFit, setIcpFit] = useLocalStorage('ct_filter_icp', '')
  const [msgStatus, setMsgStatus] = useLocalStorage('ct_filter_msg_status', '')
  const [sortField, setSortField] = useLocalStorage('ct_sort_field', 'last_name')
  const [sortDir, setSortDir] = useLocalStorage<'asc' | 'desc'>('ct_sort_dir', 'asc')

  const { data: tagsData } = useTags()

  const filters: ContactFilters = useMemo(() => ({
    search,
    tag_name: tagName,
    owner_name: ownerName,
    icp_fit: icpFit,
    message_status: msgStatus,
    sort: sortField,
    sort_dir: sortDir,
  }), [search, tagName, ownerName, icpFit, msgStatus, sortField, sortDir])

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

  // Fetch detail for whichever entity type is at the top of stack
  const isContactOpen = stack.current?.type === 'contact'
  const isCompanyOpen = stack.current?.type === 'company'
  const { data: contactDetail, isLoading: isContactLoading } = useContact(
    isContactOpen ? stack.current!.id : null
  )
  const { data: companyDetail, isLoading: isCompanyLoading } = useCompany(
    isCompanyOpen ? stack.current!.id : null
  )

  const handleFilterChange = useCallback((key: string, value: string) => {
    switch (key) {
      case 'search': setSearch(value); break
      case 'tag_name': setTagName(value); break
      case 'owner_name': setOwnerName(value); break
      case 'icp_fit': setIcpFit(value); break
      case 'message_status': setMsgStatus(value); break
    }
  }, [setSearch, setTagName, setOwnerName, setIcpFit, setMsgStatus])

  const handleSort = useCallback((field: string, dir: 'asc' | 'desc') => {
    setSortField(field)
    setSortDir(dir)
  }, [setSortField, setSortDir])

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
    { key: 'tag_name', label: 'Tag', minWidth: '70px' },
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
        onRowClick={(c) => stack.open('contact', c.id)}
        onLoadMore={() => fetchNextPage()}
        hasMore={hasNextPage}
        isLoading={isLoading || isFetchingNextPage}
        emptyText="No contacts match your filters."
      />

      <DetailModal
        isOpen={!!stack.current}
        onClose={stack.close}
        title={isContactOpen ? (contactDetail?.full_name ?? 'Contact') : isCompanyOpen ? (companyDetail?.name ?? 'Company') : ''}
        subtitle={isContactOpen ? (contactDetail?.job_title ?? undefined) : isCompanyOpen ? (companyDetail?.domain ?? undefined) : undefined}
        isLoading={isContactOpen ? isContactLoading : isCompanyLoading}
        canGoBack={stack.depth > 1}
        onBack={stack.pop}
        breadcrumb={stack.depth > 1 ? 'Back' : undefined}
      >
        {isContactOpen && contactDetail && (
          <ContactDetail contact={contactDetail} onNavigate={stack.push} />
        )}
        {isCompanyOpen && companyDetail && (
          <CompanyDetail company={companyDetail} onNavigate={stack.push} />
        )}
      </DetailModal>
    </div>
  )
}
