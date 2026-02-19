import { useReviewSummary } from '../../api/queries/useMessages'
import { useUpdateCampaign } from '../../api/queries/useCampaigns'
import { useToast } from '../../components/ui/Toast'

const CHANNEL_LABELS: Record<string, string> = {
  linkedin_connect: 'LinkedIn Invites',
  linkedin_message: 'LinkedIn Messages',
  email: 'Emails',
  call_script: 'Call Scripts',
}

interface OutreachApprovalDialogProps {
  campaignId: string
  onClose: () => void
  onApproved: () => void
}

export function OutreachApprovalDialog({ campaignId, onClose, onApproved }: OutreachApprovalDialogProps) {
  const { toast } = useToast()
  const { data: summary, isLoading } = useReviewSummary(campaignId)
  const updateMutation = useUpdateCampaign()

  const handleApprove = async () => {
    try {
      await updateMutation.mutateAsync({
        id: campaignId,
        data: { status: 'approved' },
      })
      toast('Outreach approved', 'success')
      onApproved()
    } catch {
      toast('Failed to approve outreach', 'error')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-bg border border-border rounded-xl shadow-xl max-w-md w-full mx-4 p-6" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-text mb-4">Approve Outreach</h3>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin w-6 h-6 border-2 border-accent border-t-transparent rounded-full" />
          </div>
        ) : summary ? (
          <div className="space-y-4 mb-6">
            {/* Summary stats */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-success/10 border border-success/20 rounded-lg p-3 text-center">
                <div className="text-lg font-semibold text-success">{summary.approved}</div>
                <div className="text-[10px] text-success/80 uppercase tracking-wide">Approved</div>
              </div>
              <div className="bg-error/10 border border-error/20 rounded-lg p-3 text-center">
                <div className="text-lg font-semibold text-error">{summary.rejected}</div>
                <div className="text-[10px] text-error/80 uppercase tracking-wide">Rejected</div>
              </div>
              <div className="bg-surface border border-border rounded-lg p-3 text-center">
                <div className="text-lg font-semibold text-text">{summary.active_contacts}</div>
                <div className="text-[10px] text-text-dim uppercase tracking-wide">Contacts</div>
              </div>
            </div>

            {/* Channel breakdown */}
            {Object.keys(summary.by_channel).length > 0 && (
              <div className="bg-surface-alt rounded-lg p-3">
                <div className="text-xs font-medium text-text-muted mb-2">Approved by channel</div>
                <div className="space-y-1">
                  {Object.entries(summary.by_channel).map(([ch, counts]) => (
                    <div key={ch} className="flex justify-between text-xs">
                      <span className="text-text-muted">{CHANNEL_LABELS[ch] ?? ch}</span>
                      <span className="text-text font-medium">{(counts as Record<string, number>).approved ?? 0}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {summary.excluded_contacts > 0 && (
              <div className="text-xs text-text-dim">
                {summary.excluded_contacts} contact{summary.excluded_contacts > 1 ? 's' : ''} excluded
              </div>
            )}

            {summary.approved === 0 && (
              <div className="p-3 bg-warning/10 border border-warning/20 rounded-lg text-xs text-warning">
                No approved messages. Approving outreach with 0 messages will have no effect.
              </div>
            )}
          </div>
        ) : null}

        <div className="flex gap-2">
          <button
            onClick={handleApprove}
            disabled={updateMutation.isPending || isLoading}
            className="flex-1 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent-hover disabled:opacity-50"
          >
            {updateMutation.isPending ? 'Approving...' : 'Approve Outreach'}
          </button>
          <button
            onClick={onClose}
            disabled={updateMutation.isPending}
            className="px-4 py-2 bg-surface border border-border text-text text-sm rounded-lg hover:bg-surface-alt"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
