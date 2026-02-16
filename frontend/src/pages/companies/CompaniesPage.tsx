import { useMemo, useCallback } from 'react'
import { useParams } from 'react-router'
import { useCompanies, useCompany, type CompanyListItem, type CompanyFilters } from '../../api/queries/useCompanies'
import { useContact } from '../../api/queries/useContacts'
import { useBatches } from '../../api/queries/useBatches'
import { useLocalStorage } from '../../hooks/useLocalStorage'
import { useEntityStack } from '../../hooks/useEntityStack'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { FilterBar, type FilterConfig } from '../../components/ui/FilterBar'
import { Badge } from '../../components/ui/Badge'
import { CompanyDetail } from './CompanyDetail'
import { ContactDetail } from '../contacts/ContactDetail'
import { DetailModal } from '../../components/ui/DetailModal'
import {
  STATUS_DISPLAY,
  TIER_DISPLAY,
  filterOptions,
} from '../../lib/display'

export function CompaniesPage() {
  const { namespace } = useParams<{ namespace: string }>()

  // Entity stack for cross-entity modal navigation
  const stack = useEntityStack('company')

  // Filters persisted in localStorage
  const [search, setSearch] = useLocalStorage('co_filter_search', '')
  const [status, setStatus] = useLocalStorage('co_filter_status', '')
  const [tier, setTier] = useLocalStorage('co_filter_tier', '')
  const [batchName, setBatchName] = useLocalStorage('co_filter_batch', '')
  const [ownerName, setOwnerName] = useLocalStorage('co_filter_owner', '')
  const [sortField, setSortField] = useLocalStorage('co_sort_field', 'name')
  const [sortDir, setSortDir] = useLocalStorage<'asc' | 'desc'>('co_sort_dir', 'asc')

  const { data: batchesData } = useBatches()

  const filters: CompanyFilters = useMemo(() => ({
    search,
    status,
    tier,
    batch_name: batchName,
    owner_name: ownerName,
    sort: sortField,
    sort_dir: sortDir,
  }), [search, status, tier, batchName, ownerName, sortField, sortDir])

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

  // Fetch detail for whichever entity type is at the top of stack
  const isCompanyOpen = stack.current?.type === 'company'
  const isContactOpen = stack.current?.type === 'contact'
  const { data: companyDetail, isLoading: isCompanyLoading } = useCompany(
    isCompanyOpen ? stack.current!.id : null
  )
  const { data: contactDetail, isLoading: isContactLoading } = useContact(
    isContactOpen ? stack.current!.id : null
  )

  const handleFilterChange = useCallback((key: string, value: string) => {
    switch (key) {
      case 'search': setSearch(value); break
      case 'status': setStatus(value); break
      case 'tier': setTier(value); break
      case 'batch_name': setBatchName(value); break
      case 'owner_name': setOwnerName(value); break
    }
  }, [setSearch, setStatus, setTier, setBatchName, setOwnerName])

  const handleSort = useCallback((field: string, dir: 'asc' | 'desc') => {
    setSortField(field)
    setSortDir(dir)
  }, [setSortField, setSortDir])

  const filterConfigs: FilterConfig[] = useMemo(() => [
    { key: 'search', label: 'companies', type: 'search' as const, placeholder: 'Search name or domain...' },
    { key: 'status', label: 'Status', type: 'select' as const, options: filterOptions(STATUS_DISPLAY) },
    { key: 'tier', label: 'Tier', type: 'select' as const, options: filterOptions(TIER_DISPLAY) },
    { key: 'batch_name', label: 'Batch', type: 'select' as const, options: (batchesData?.batches ?? []).map((b) => ({ value: b.name, label: b.name })) },
    { key: 'owner_name', label: 'Owner', type: 'select' as const, options: (batchesData?.owners ?? []).map((o) => ({ value: o.name, label: o.name })) },
  ], [batchesData])

  const columns: Column<CompanyListItem>[] = useMemo(() => [
    { key: 'name', label: 'Name', sortKey: 'name', minWidth: '140px' },
    { key: 'domain', label: 'Domain', sortKey: 'domain', minWidth: '100px', render: (c) => c.domain ? (
      <a href={`https://${c.domain}`} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="text-accent-cyan hover:underline truncate block">{c.domain}</a>
    ) : '-' },
    { key: 'status', label: 'Status', sortKey: 'status', minWidth: '110px', shrink: false, render: (c) => <Badge variant="status" value={c.status} /> },
    { key: 'tier', label: 'Tier', sortKey: 'tier', minWidth: '110px', shrink: false, render: (c) => <Badge variant="tier" value={c.tier} /> },
    { key: 'owner_name', label: 'Owner', minWidth: '70px' },
    { key: 'batch_name', label: 'Batch', minWidth: '70px' },
    { key: 'industry', label: 'Industry', minWidth: '90px' },
    { key: 'hq_country', label: 'HQ', sortKey: 'hq_country', minWidth: '40px' },
    { key: 'triage_score', label: 'Score', sortKey: 'triage_score', minWidth: '55px', render: (c) => c.triage_score != null ? c.triage_score.toFixed(1) : '-' },
    { key: 'contact_count', label: 'Contacts', sortKey: 'contact_count', minWidth: '55px' },
  ], [])

  return (
    <div className="flex flex-col h-full min-h-0">
      <FilterBar
        filters={filterConfigs}
        values={{ search, status, tier, batch_name: batchName, owner_name: ownerName }}
        onChange={handleFilterChange}
        total={total}
        action={
          namespace && (
            <a
              href={`/${namespace}/enrich`}
              className="text-xs text-accent-cyan hover:underline ml-2"
            >
              Enrich Selection
            </a>
          )
        }
      />

      <DataTable
        columns={columns}
        data={allCompanies}
        sort={{ field: sortField, dir: sortDir }}
        onSort={handleSort}
        onRowClick={(c) => stack.open('company', c.id)}
        onLoadMore={() => fetchNextPage()}
        hasMore={hasNextPage}
        isLoading={isLoading || isFetchingNextPage}
        emptyText="No companies match your filters."
      />

      <DetailModal
        isOpen={!!stack.current}
        onClose={stack.close}
        title={isCompanyOpen ? (companyDetail?.name ?? 'Company') : isContactOpen ? (contactDetail?.full_name ?? 'Contact') : ''}
        subtitle={isCompanyOpen ? (companyDetail?.domain ?? undefined) : isContactOpen ? (contactDetail?.job_title ?? undefined) : undefined}
        isLoading={isCompanyOpen ? isCompanyLoading : isContactLoading}
        canGoBack={stack.depth > 1}
        onBack={stack.pop}
        breadcrumb={stack.depth > 1 ? 'Back' : undefined}
      >
        {isCompanyOpen && companyDetail && (
          <CompanyDetail company={companyDetail} onNavigate={stack.push} />
        )}
        {isContactOpen && contactDetail && (
          <ContactDetail contact={contactDetail} onNavigate={stack.push} />
        )}
      </DetailModal>
    </div>
  )
}
