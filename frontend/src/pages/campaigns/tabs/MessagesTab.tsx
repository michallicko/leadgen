import { useMemo, useCallback, useEffect, useState } from 'react'
import { FilterBar, type FilterConfig } from '../../../components/ui/FilterBar'
import { useMessages, useBatchUpdateMessages, type Message, type MessageFilters } from '../../../api/queries/useMessages'
import { useToast } from '../../../components/ui/Toast'
import { ContactGroup } from '../../messages/ContactGroup'
import { REVIEW_STATUS_DISPLAY, filterOptions } from '../../../lib/display'

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

interface Props {
  campaignId: string
  onNavigate: (type: 'company' | 'contact', id: string) => void
}

export function MessagesTab({ campaignId, onNavigate }: Props) {
  const { toast } = useToast()

  const [status, setStatus] = useState('draft')
  const [channel, setChannel] = useState('')

  const filters: MessageFilters = useMemo(() => ({
    campaign_id: campaignId,
    status: status || undefined,
    channel: channel || undefined,
  }), [campaignId, status, channel])

  const { data, isLoading, refetch, isRefetching } = useMessages(filters)
  const batchMutation = useBatchUpdateMessages()

  // Auto-load on mount
  useEffect(() => { refetch() }, [refetch])

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
    return Array.from(map.values()).sort(
      (a, b) => (b.contactScore ?? 0) - (a.contactScore ?? 0)
    )
  }, [data])

  const totalMessages = data?.messages.length ?? 0
  const totalContacts = groups.length
  const draftCount = data?.messages.filter((m) => m.status === 'draft').length ?? 0

  // Bulk approve all visible draft A variants
  const allDraftAIds = useMemo(
    () => (data?.messages ?? [])
      .filter((m) => m.status === 'draft' && m.variant === 'A')
      .map((m) => m.id),
    [data],
  )

  const handleBulkApprove = useCallback(async () => {
    if (allDraftAIds.length === 0) {
      toast('No draft A variants to approve', 'info')
      return
    }
    if (!confirm(`Approve ${allDraftAIds.length} variant A message(s)?`)) return
    try {
      await batchMutation.mutateAsync({
        ids: allDraftAIds,
        fields: { status: 'approved', approved_at: new Date().toISOString() },
      })
      toast(`${allDraftAIds.length} messages approved`, 'success')
    } catch {
      toast('Bulk approve failed', 'error')
    }
  }, [allDraftAIds, batchMutation, toast])

  const handleFilterChange = useCallback((key: string, value: string) => {
    switch (key) {
      case 'status': setStatus(value); break
      case 'channel': setChannel(value); break
    }
  }, [])

  const filterConfigs: FilterConfig[] = useMemo(() => [
    { key: 'status', label: 'Status', type: 'select' as const, options: filterOptions(REVIEW_STATUS_DISPLAY) },
    { key: 'channel', label: 'Channel', type: 'select' as const, options: CHANNEL_OPTIONS },
  ], [])

  return (
    <div className="flex flex-col min-h-0 -mx-6 -mt-5">
      <FilterBar
        filters={filterConfigs}
        values={{ status, channel }}
        onChange={handleFilterChange}
        action={
          <div className="flex items-center gap-2 ml-auto">
            <button
              onClick={() => refetch()}
              disabled={isLoading || isRefetching}
              className="px-3 py-1.5 text-xs bg-accent hover:bg-accent-hover text-white rounded-md disabled:opacity-50 transition-colors"
            >
              {isLoading || isRefetching ? 'Loading...' : 'Refresh'}
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
          </div>
        }
      />

      {totalMessages > 0 && (
        <div className="flex items-center gap-4 text-xs text-text-muted mb-3 px-6 pt-1">
          <span>{totalContacts} contact{totalContacts !== 1 ? 's' : ''}</span>
          <span>{totalMessages} message{totalMessages !== 1 ? 's' : ''}</span>
          <span>{draftCount} draft{draftCount !== 1 ? 's' : ''}</span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto space-y-4 min-h-0 px-6 pb-4">
        {isLoading || isRefetching ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-border border-t-accent rounded-full animate-spin" />
          </div>
        ) : groups.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-text-dim">
            <div className="text-4xl mb-2">{'\u{1F4ED}'}</div>
            <div className="text-sm">
              {data ? 'No messages match your filters.' : 'Loading messages...'}
            </div>
          </div>
        ) : (
          groups.map((g) => (
            <ContactGroup
              key={g.contactId}
              contactName={g.contactName}
              contactTitle={g.contactTitle}
              contactScore={g.contactScore}
              contactIcp={g.contactIcp}
              linkedinUrl={g.linkedinUrl}
              companyName={g.companyName}
              companyTier={g.companyTier}
              messages={g.messages}
              onContactClick={g.contactId !== 'unknown' ? () => onNavigate('contact', g.contactId) : undefined}
              onCompanyClick={g.companyId ? () => onNavigate('company', g.companyId!) : undefined}
            />
          ))
        )}
      </div>
    </div>
  )
}
