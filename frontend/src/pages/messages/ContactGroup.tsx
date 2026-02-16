import { useCallback, useMemo } from 'react'
import { Badge } from '../../components/ui/Badge'
import { MessageCard } from './MessageCard'
import { useBatchUpdateMessages, type Message } from '../../api/queries/useMessages'
import { useToast } from '../../components/ui/Toast'

interface ContactGroupProps {
  contactName: string
  contactTitle: string | null
  contactScore: number | null
  contactIcp: string | null
  linkedinUrl: string | null
  companyName: string | null
  companyTier: string | null
  messages: Message[]
  onContactClick?: () => void
  onCompanyClick?: () => void
}

export function ContactGroup({
  contactName, contactTitle, contactScore, contactIcp,
  linkedinUrl, companyName, companyTier, messages,
  onContactClick, onCompanyClick,
}: ContactGroupProps) {
  const { toast } = useToast()
  const batchMutation = useBatchUpdateMessages()

  const draftAIds = useMemo(
    () => messages
      .filter((m) => m.status === 'draft' && m.variant === 'A')
      .map((m) => m.id),
    [messages],
  )

  const handleApproveAllA = useCallback(async () => {
    if (draftAIds.length === 0) return
    try {
      await batchMutation.mutateAsync({
        ids: draftAIds,
        fields: { status: 'approved', approved_at: new Date().toISOString() },
      })
      toast(`${draftAIds.length} message(s) approved`, 'success')
    } catch {
      toast('Bulk approve failed', 'error')
    }
  }, [draftAIds, batchMutation, toast])

  return (
    <div className="border border-border-solid rounded-lg bg-surface/50 overflow-hidden">
      {/* Contact header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-surface-alt/50 border-b border-border-solid flex-wrap">
        <button
          onClick={onContactClick}
          className="text-sm font-medium text-text hover:text-accent-cyan transition-colors"
        >
          {contactName}
        </button>
        {contactTitle && <span className="text-xs text-text-muted">{contactTitle}</span>}
        {contactScore != null && (
          <span className="text-xs font-medium text-accent-cyan">{contactScore}</span>
        )}
        <Badge variant="icp" value={contactIcp} />
        {companyName && (
          <button
            onClick={onCompanyClick}
            className="text-xs text-text-dim hover:text-accent-cyan transition-colors"
          >
            {companyName}
          </button>
        )}
        {companyTier && <Badge variant="tier" value={companyTier} />}
        {linkedinUrl && (
          <a
            href={linkedinUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-accent-cyan hover:underline ml-auto"
            onClick={(e) => e.stopPropagation()}
          >
            LinkedIn
          </a>
        )}
        {draftAIds.length > 0 && (
          <button
            onClick={handleApproveAllA}
            disabled={batchMutation.isPending}
            className="ml-auto px-2.5 py-1 text-xs bg-success/10 text-success border border-success/30 rounded hover:bg-success/20 transition-colors disabled:opacity-50"
          >
            Approve all A ({draftAIds.length})
          </button>
        )}
      </div>

      {/* Messages grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-3">
        {messages.map((m) => (
          <MessageCard key={m.id} message={m} />
        ))}
      </div>
    </div>
  )
}
