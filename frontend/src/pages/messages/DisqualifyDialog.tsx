import { useState } from 'react'
import { useDisqualifyContact } from '../../api/queries/useMessages'
import { useToast } from '../../components/ui/Toast'

interface DisqualifyDialogProps {
  campaignId: string
  contactId: string
  contactName: string
  onClose: () => void
  onDisqualified: (scope: 'campaign' | 'global') => void
}

export function DisqualifyDialog({
  campaignId, contactId, contactName, onClose, onDisqualified,
}: DisqualifyDialogProps) {
  const { toast } = useToast()
  const mutation = useDisqualifyContact()
  const [scope, setScope] = useState<'campaign' | 'global'>('campaign')
  const [reason, setReason] = useState('')

  const handleConfirm = async () => {
    try {
      const result = await mutation.mutateAsync({
        campaignId,
        contactId,
        scope,
        reason: reason.trim() || undefined,
      })
      toast(
        scope === 'global'
          ? `${contactName} disqualified globally (${result.messages_rejected} messages rejected)`
          : `${contactName} excluded from campaign (${result.messages_rejected} messages rejected)`,
        'success',
      )
      onDisqualified(scope)
    } catch {
      toast('Failed to disqualify contact', 'error')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-bg border border-border rounded-xl shadow-xl max-w-md w-full mx-4 p-6" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-text mb-4">
          Disqualify {contactName}
        </h3>

        <div className="space-y-3 mb-4">
          <label
            className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
              scope === 'campaign' ? 'bg-accent/10 border-accent' : 'bg-surface border-border hover:bg-surface-alt'
            }`}
            onClick={() => setScope('campaign')}
          >
            <input type="radio" checked={scope === 'campaign'} onChange={() => setScope('campaign')} className="mt-0.5" />
            <div>
              <div className="text-sm font-medium text-text">Skip in this campaign</div>
              <div className="text-xs text-text-muted mt-0.5">
                Exclude from this campaign only. All pending messages will be rejected.
              </div>
            </div>
          </label>

          <label
            className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
              scope === 'global' ? 'bg-error/10 border-error' : 'bg-surface border-border hover:bg-surface-alt'
            }`}
            onClick={() => setScope('global')}
          >
            <input type="radio" checked={scope === 'global'} onChange={() => setScope('global')} className="mt-0.5" />
            <div>
              <div className="text-sm font-medium text-text flex items-center gap-1.5">
                Disqualify globally
                <span className="text-[10px] px-1.5 py-0.5 bg-error/15 text-error rounded">permanent</span>
              </div>
              <div className="text-xs text-text-muted mt-0.5">
                Remove from this campaign AND hide from all future campaigns.
              </div>
            </div>
          </label>
        </div>

        <div className="mb-4">
          <label className="block text-xs font-medium text-text-muted mb-1">
            Reason <span className="text-text-dim">(optional)</span>
          </label>
          <input
            type="text"
            value={reason}
            onChange={e => setReason(e.target.value)}
            placeholder="e.g. no longer at company, not a fit..."
            className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleConfirm}
            disabled={mutation.isPending}
            className={`flex-1 px-4 py-2 text-white text-sm font-medium rounded-lg disabled:opacity-50 ${
              scope === 'global'
                ? 'bg-error hover:bg-error/90'
                : 'bg-accent hover:bg-accent-hover'
            }`}
          >
            {mutation.isPending ? 'Processing...' : scope === 'global' ? 'Disqualify Globally' : 'Exclude from Campaign'}
          </button>
          <button
            onClick={onClose}
            disabled={mutation.isPending}
            className="px-4 py-2 bg-surface border border-border text-text text-sm rounded-lg hover:bg-surface-alt"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
