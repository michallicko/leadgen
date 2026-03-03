import { useMemo, useCallback, useEffect, useState, useRef } from 'react'
import { FilterBar, type FilterConfig } from '../../components/ui/FilterBar'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { useMessages, useBatchUpdateMessages, type Message, type MessageFilters } from '../../api/queries/useMessages'
import { useTags } from '../../api/queries/useTags'
import { useCampaigns } from '../../api/queries/useCampaigns'
import { useOnboardingStatus } from '../../hooks/useOnboarding'
import { useLocalStorage } from '../../hooks/useLocalStorage'
import { useToast } from '../../components/ui/Toast'
import { useEntityStack } from '../../hooks/useEntityStack'
import { useCompany } from '../../api/queries/useCompanies'
import { useContact } from '../../api/queries/useContacts'
import { DetailModal } from '../../components/ui/DetailModal'
import { CompanyDetail } from '../companies/CompanyDetail'
import { ContactDetail } from '../contacts/ContactDetail'
import { ContactGroup } from './ContactGroup'
import { MessagesEmptyState } from '../../components/onboarding/SmartEmptyState'
import { REVIEW_STATUS_DISPLAY, filterOptions } from '../../lib/display'
import { KeyboardShortcutsHelp } from './KeyboardShortcutsHelp'

interface ContactMessages {
  contactId: string
  contactName: string
  contactTitle: string | null
  contactScore: number | null
  contactIcp: string | null
  linkedinUrl: string | null
  companyId: string | null
  companyName: string | null
  companyTier: string | null
  messages: Message[]
}

const CHANNEL_OPTIONS = [
  { value: 'linkedin_connect', label: 'LI Connect' },
  { value: 'linkedin_message', label: 'LI Message' },
  { value: 'email', label: 'Email' },
  { value: 'call_script', label: 'Call Script' },
]

export function MessagesPage() {
  const { toast } = useToast()
  const stack = useEntityStack('contact')
  const [showBulkApproveConfirm, setShowBulkApproveConfirm] = useState(false)
  const [showBulkRejectConfirm, setShowBulkRejectConfirm] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [showShortcutsHelp, setShowShortcutsHelp] = useState(false)
  const [focusedGroupIndex, setFocusedGroupIndex] = useState(-1)
  const groupRefs = useRef<(HTMLDivElement | null)[]>([])

  // Filters
  const [ownerName, setOwnerName] = useLocalStorage('msg_filter_owner', '')
  const [status, setStatus] = useLocalStorage('msg_filter_status', 'draft')
  const [channel, setChannel] = useLocalStorage('msg_filter_channel', '')
  const [campaignId, setCampaignId] = useLocalStorage('msg_filter_campaign', '')
  const [contactSearch, setContactSearch] = useLocalStorage('msg_filter_contact', '')

  const filters: MessageFilters = useMemo(() => ({
    status: status || undefined,
    owner_name: ownerName || undefined,
    channel: channel || undefined,
    campaign_id: campaignId || undefined,
  }), [status, ownerName, channel, campaignId])

  const { data, isLoading, refetch, isRefetching } = useMessages(filters)
  const { data: tagsData } = useTags()
  const { data: campaignsData } = useCampaigns()
  const { data: onboardingStatus } = useOnboardingStatus()
  const batchMutation = useBatchUpdateMessages()

  // Group messages by contact
  const groups: ContactMessages[] = useMemo(() => {
    if (!data?.messages) return []

    const map = new Map<string, ContactMessages>()
    for (const m of data.messages) {
      const cid = m.contact.id ?? 'unknown'
      let group = map.get(cid)
      if (!group) {
        group = {
          contactId: cid,
          contactName: m.contact.full_name || 'Unknown',
          contactTitle: m.contact.job_title,
          contactScore: m.contact.contact_score,
          contactIcp: m.contact.icp_fit,
          linkedinUrl: m.contact.linkedin_url,
          companyId: m.company?.id ?? null,
          companyName: m.company?.name ?? null,
          companyTier: m.company?.tier ?? null,
          messages: [],
        }
        map.set(cid, group)
      }
      group.messages.push(m)
    }

    let result = Array.from(map.values()).sort(
      (a, b) => (b.contactScore ?? 0) - (a.contactScore ?? 0)
    )

    // Client-side contact name filter
    if (contactSearch.trim()) {
      const q = contactSearch.toLowerCase()
      result = result.filter(
        (g) =>
          g.contactName.toLowerCase().includes(q) ||
          (g.companyName && g.companyName.toLowerCase().includes(q))
      )
    }

    return result
  }, [data, contactSearch])

  // Summary stats
  const totalMessages = data?.messages.length ?? 0
  const totalContacts = groups.length
  const draftCount = data?.messages.filter((m) => m.status === 'draft').length ?? 0

  // All visible message IDs (for select-all)
  const allVisibleIds = useMemo(
    () => groups.flatMap((g) => g.messages.map((m) => m.id)),
    [groups],
  )

  // Bulk approve all visible draft A variants
  const allDraftAIds = useMemo(
    () => (data?.messages ?? [])
      .filter((m) => m.status === 'draft' && m.variant === 'A')
      .map((m) => m.id),
    [data],
  )

  // Draft IDs in the visible set (for reject all)
  const allVisibleDraftIds = useMemo(
    () => groups.flatMap((g) => g.messages.filter((m) => m.status === 'draft').map((m) => m.id)),
    [groups],
  )

  // Selection helpers
  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const toggleSelectAll = useCallback(() => {
    setSelectedIds((prev) => {
      if (prev.size === allVisibleIds.length) return new Set()
      return new Set(allVisibleIds)
    })
  }, [allVisibleIds])

  const selectedDraftIds = useMemo(
    () => {
      const draftSet = new Set(allVisibleDraftIds)
      return Array.from(selectedIds).filter((id) => draftSet.has(id))
    },
    [selectedIds, allVisibleDraftIds],
  )

  const handleBulkApprove = useCallback(() => {
    if (allDraftAIds.length === 0) {
      toast('No draft A variants to approve', 'info')
      return
    }
    setShowBulkApproveConfirm(true)
  }, [allDraftAIds, toast])

  const executeBulkApprove = useCallback(async () => {
    setShowBulkApproveConfirm(false)
    try {
      await batchMutation.mutateAsync({
        ids: allDraftAIds,
        fields: { status: 'approved', approved_at: new Date().toISOString() },
      })
      toast(`${allDraftAIds.length} messages approved`, 'success')
      setSelectedIds(new Set())
    } catch {
      toast('Bulk approve failed', 'error')
    }
  }, [allDraftAIds, batchMutation, toast])

  const handleBulkReject = useCallback(() => {
    if (allVisibleDraftIds.length === 0) {
      toast('No drafts to reject', 'info')
      return
    }
    setShowBulkRejectConfirm(true)
  }, [allVisibleDraftIds, toast])

  const executeBulkReject = useCallback(async () => {
    setShowBulkRejectConfirm(false)
    try {
      await batchMutation.mutateAsync({
        ids: allVisibleDraftIds,
        fields: { status: 'rejected', review_notes: 'Bulk rejected' },
      })
      toast(`${allVisibleDraftIds.length} messages rejected`, 'success')
      setSelectedIds(new Set())
    } catch {
      toast('Bulk reject failed', 'error')
    }
  }, [allVisibleDraftIds, batchMutation, toast])

  // Bulk approve selected
  const handleBulkApproveSelected = useCallback(async () => {
    if (selectedDraftIds.length === 0) {
      toast('No selected drafts to approve', 'info')
      return
    }
    try {
      await batchMutation.mutateAsync({
        ids: selectedDraftIds,
        fields: { status: 'approved', approved_at: new Date().toISOString() },
      })
      toast(`${selectedDraftIds.length} selected messages approved`, 'success')
      setSelectedIds(new Set())
    } catch {
      toast('Bulk approve failed', 'error')
    }
  }, [selectedDraftIds, batchMutation, toast])

  // Bulk reject selected
  const handleBulkRejectSelected = useCallback(async () => {
    if (selectedDraftIds.length === 0) {
      toast('No selected drafts to reject', 'info')
      return
    }
    try {
      await batchMutation.mutateAsync({
        ids: selectedDraftIds,
        fields: { status: 'rejected', review_notes: 'Bulk rejected' },
      })
      toast(`${selectedDraftIds.length} selected messages rejected`, 'success')
      setSelectedIds(new Set())
    } catch {
      toast('Bulk reject failed', 'error')
    }
  }, [selectedDraftIds, batchMutation, toast])

  // Keyboard shortcuts (BL-182)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (e.ctrlKey || e.metaKey || e.altKey) return

      switch (e.key) {
        case '?':
          e.preventDefault()
          setShowShortcutsHelp((v) => !v)
          break
        case 'j':
          e.preventDefault()
          setFocusedGroupIndex((prev) => {
            const next = Math.min(prev + 1, groups.length - 1)
            groupRefs.current[next]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
            return next
          })
          break
        case 'k':
          e.preventDefault()
          setFocusedGroupIndex((prev) => {
            const next = Math.max(prev - 1, 0)
            groupRefs.current[next]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
            return next
          })
          break
        case 'a':
          e.preventDefault()
          // Approve focused group's draft A messages
          if (focusedGroupIndex >= 0 && focusedGroupIndex < groups.length) {
            const group = groups[focusedGroupIndex]
            const draftAIds = group.messages
              .filter((m) => m.status === 'draft' && m.variant === 'A')
              .map((m) => m.id)
            if (draftAIds.length > 0) {
              batchMutation.mutateAsync({
                ids: draftAIds,
                fields: { status: 'approved', approved_at: new Date().toISOString() },
              }).then(() => toast(`${draftAIds.length} approved`, 'success'))
                .catch(() => toast('Approve failed', 'error'))
            }
          }
          break
        case 'r':
          e.preventDefault()
          // Reject focused group's draft messages
          if (focusedGroupIndex >= 0 && focusedGroupIndex < groups.length) {
            const group = groups[focusedGroupIndex]
            const draftIds = group.messages
              .filter((m) => m.status === 'draft')
              .map((m) => m.id)
            if (draftIds.length > 0) {
              batchMutation.mutateAsync({
                ids: draftIds,
                fields: { status: 'rejected', review_notes: 'Keyboard reject' },
              }).then(() => toast(`${draftIds.length} rejected`, 'success'))
                .catch(() => toast('Reject failed', 'error'))
            }
          }
          break
        case 'A':
          e.preventDefault()
          handleBulkApprove()
          break
        case 'Escape':
          setShowShortcutsHelp(false)
          setFocusedGroupIndex(-1)
          break
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [handleBulkApprove, groups, focusedGroupIndex, batchMutation, toast])

  const handleFilterChange = useCallback((key: string, value: string) => {
    switch (key) {
      case 'owner_name': setOwnerName(value); break
      case 'status': setStatus(value); break
      case 'channel': setChannel(value); break
      case 'campaign_id': setCampaignId(value); break
      case 'contact_search': setContactSearch(value); break
    }
  }, [setOwnerName, setStatus, setChannel, setCampaignId, setContactSearch])

  const campaignOptions = useMemo(
    () => (campaignsData?.campaigns ?? []).map((c) => ({ value: c.id, label: c.name })),
    [campaignsData],
  )

  const filterConfigs: FilterConfig[] = useMemo(() => [
    { key: 'owner_name', label: 'Owner', type: 'select' as const, options: (tagsData?.owners ?? []).map((o) => ({ value: o.name, label: o.name })) },
    { key: 'status', label: 'Status', type: 'select' as const, options: filterOptions(REVIEW_STATUS_DISPLAY) },
    { key: 'channel', label: 'Channel', type: 'select' as const, options: CHANNEL_OPTIONS },
    { key: 'campaign_id', label: 'Campaign', type: 'select' as const, options: campaignOptions },
    { key: 'contact_search', label: 'Contact / Company', type: 'search' as const, placeholder: 'Filter by contact or company...' },
  ], [tagsData, campaignOptions])

  // Entity detail modal
  const isCompanyOpen = stack.current?.type === 'company'
  const isContactOpen = stack.current?.type === 'contact'
  const { data: companyDetail, isLoading: isCompanyLoading } = useCompany(
    isCompanyOpen ? stack.current!.id : null
  )
  const { data: contactDetail, isLoading: isContactLoading } = useContact(
    isContactOpen ? stack.current!.id : null
  )

  // Show smart empty state when namespace has no contacts (no messages possible)
  const namespaceHasNoContacts =
    onboardingStatus !== undefined && onboardingStatus.contact_count === 0
  if (namespaceHasNoContacts && !isLoading) {
    return <MessagesEmptyState />
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Filter bar */}
      <FilterBar
        filters={filterConfigs}
        values={{ owner_name: ownerName, status, channel, campaign_id: campaignId, contact_search: contactSearch }}
        onChange={handleFilterChange}
        action={
          <div className="flex items-center gap-2 ml-auto">
            <button
              onClick={() => refetch()}
              disabled={isLoading || isRefetching}
              className="px-3 py-1.5 text-xs bg-accent hover:bg-accent-hover text-white rounded-md disabled:opacity-50 transition-colors"
            >
              {isLoading || isRefetching ? 'Loading...' : 'Load Messages'}
            </button>
            {allDraftAIds.length > 0 && (
              <button
                onClick={handleBulkApprove}
                disabled={batchMutation.isPending}
                className="px-3 py-1.5 text-xs bg-success/10 text-success border border-success/30 rounded-md hover:bg-success/20 transition-colors disabled:opacity-50"
              >
                Approve All A ({allDraftAIds.length})
              </button>
            )}
            {allVisibleDraftIds.length > 0 && (
              <button
                onClick={handleBulkReject}
                disabled={batchMutation.isPending}
                className="px-3 py-1.5 text-xs bg-error/10 text-error border border-error/30 rounded-md hover:bg-error/20 transition-colors disabled:opacity-50"
              >
                Reject All ({allVisibleDraftIds.length})
              </button>
            )}
            <button
              onClick={() => setShowShortcutsHelp(true)}
              className="px-2 py-1.5 text-xs text-text-dim hover:text-text-muted rounded transition-colors"
              title="Keyboard shortcuts (?)"
            >
              <kbd className="px-1.5 py-0.5 bg-surface-alt rounded text-[10px] border border-border-solid">?</kbd>
            </button>
          </div>
        }
      />

      {/* Summary bar with select-all */}
      {totalMessages > 0 && (
        <div className="flex items-center gap-4 text-xs text-text-muted mb-3 px-1">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={selectedIds.size > 0 && selectedIds.size === allVisibleIds.length}
              ref={(el) => {
                if (el) el.indeterminate = selectedIds.size > 0 && selectedIds.size < allVisibleIds.length
              }}
              onChange={toggleSelectAll}
              className="w-3.5 h-3.5 rounded border-border-solid accent-accent"
            />
            <span>Select all</span>
          </label>
          <span>{totalContacts} contact{totalContacts !== 1 ? 's' : ''}</span>
          <span>{totalMessages} message{totalMessages !== 1 ? 's' : ''}</span>
          <span>{draftCount} draft{draftCount !== 1 ? 's' : ''}</span>
          {selectedIds.size > 0 && (
            <div className="flex items-center gap-2 ml-auto">
              <span className="font-medium text-text">{selectedIds.size} selected</span>
              <button
                onClick={handleBulkApproveSelected}
                disabled={batchMutation.isPending || selectedDraftIds.length === 0}
                className="px-2.5 py-1 text-xs bg-success/10 text-success border border-success/30 rounded hover:bg-success/20 transition-colors disabled:opacity-50"
              >
                Approve ({selectedDraftIds.length})
              </button>
              <button
                onClick={handleBulkRejectSelected}
                disabled={batchMutation.isPending || selectedDraftIds.length === 0}
                className="px-2.5 py-1 text-xs bg-error/10 text-error border border-error/30 rounded hover:bg-error/20 transition-colors disabled:opacity-50"
              >
                Reject ({selectedDraftIds.length})
              </button>
              <button
                onClick={() => setSelectedIds(new Set())}
                className="px-2.5 py-1 text-xs text-text-muted hover:text-text"
              >
                Clear
              </button>
            </div>
          )}
        </div>
      )}

      {/* Message groups */}
      <div className="flex-1 overflow-y-auto space-y-4 min-h-0">
        {isLoading || isRefetching ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-border border-t-accent rounded-full animate-spin" />
          </div>
        ) : groups.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-text-dim">
            <div className="text-4xl mb-2">{'\u{1F4ED}'}</div>
            <div className="text-sm">
              {data ? 'No messages match your filters.' : 'Click "Load Messages" to start.'}
            </div>
          </div>
        ) : (
          groups.map((g, idx) => (
            <div
              key={g.contactId}
              ref={(el) => { groupRefs.current[idx] = el }}
              className={focusedGroupIndex === idx ? 'ring-2 ring-accent/50 rounded-lg' : ''}
            >
              <ContactGroup
                contactName={g.contactName}
                contactTitle={g.contactTitle}
                contactScore={g.contactScore}
                contactIcp={g.contactIcp}
                linkedinUrl={g.linkedinUrl}
                companyName={g.companyName}
                companyTier={g.companyTier}
                messages={g.messages}
                selectedIds={selectedIds}
                onToggleSelect={toggleSelect}
                onContactClick={g.contactId !== 'unknown' ? () => stack.open('contact', g.contactId) : undefined}
                onCompanyClick={g.companyId ? () => stack.open('company', g.companyId!) : undefined}
              />
            </div>
          ))
        )}
      </div>

      {/* Entity detail modal */}
      <DetailModal
        isOpen={!!stack.current}
        onClose={stack.close}
        title={
          isCompanyOpen ? (companyDetail?.name ?? 'Company')
          : isContactOpen ? (contactDetail?.full_name ?? 'Contact')
          : ''
        }
        subtitle={
          isCompanyOpen ? (companyDetail?.domain ?? undefined)
          : isContactOpen ? (contactDetail?.job_title ?? undefined)
          : undefined
        }
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

      <ConfirmDialog
        open={showBulkApproveConfirm}
        title="Bulk approve messages"
        message={`Approve ${allDraftAIds.length} variant A message(s)? This will mark them as ready for outreach.`}
        confirmLabel="Approve All"
        onConfirm={executeBulkApprove}
        onCancel={() => setShowBulkApproveConfirm(false)}
      />

      <ConfirmDialog
        open={showBulkRejectConfirm}
        title="Bulk reject messages"
        message={`Reject ${allVisibleDraftIds.length} draft message(s)? This action can be undone by resetting to draft.`}
        confirmLabel="Reject All"
        onConfirm={executeBulkReject}
        onCancel={() => setShowBulkRejectConfirm(false)}
      />

      {showShortcutsHelp && (
        <KeyboardShortcutsHelp onClose={() => setShowShortcutsHelp(false)} />
      )}
    </div>
  )
}
