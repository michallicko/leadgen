/**
 * CorrectiveActionButtons — approve, retry, or disqualify an entity.
 * Calls POST /api/enrich/resolve. Reused in corrective modal and company detail.
 */

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'

interface CorrectiveActionButtonsProps {
  companyId: string
  onSuccess?: () => void
}

type Action = 'approve' | 'retry' | 'skip'

export function CorrectiveActionButtons({ companyId, onSuccess }: CorrectiveActionButtonsProps) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState<Action | null>(null)

  const mutation = useMutation({
    mutationFn: (action: Action) =>
      apiFetch('/enrich/resolve', {
        method: 'POST',
        body: { company_id: companyId, action },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stage-health'] })
      queryClient.invalidateQueries({ queryKey: ['enrich-estimate'] })
      queryClient.invalidateQueries({ queryKey: ['companies'] })
      setConfirming(null)
      onSuccess?.()
    },
  })

  const handleClick = (action: Action) => {
    if (action === 'skip' && confirming !== 'skip') {
      setConfirming('skip')
      return
    }
    mutation.mutate(action)
  }

  return (
    <div className="flex items-center gap-1.5">
      <button
        onClick={() => handleClick('approve')}
        disabled={mutation.isPending}
        className="px-2 py-1 text-xs font-medium rounded border border-success/30 bg-success/10 text-success hover:bg-success/20 transition-colors disabled:opacity-50"
      >
        Approve
      </button>
      <button
        onClick={() => handleClick('retry')}
        disabled={mutation.isPending}
        className="px-2 py-1 text-xs font-medium rounded border border-warning/30 bg-warning/10 text-warning hover:bg-warning/20 transition-colors disabled:opacity-50"
      >
        Retry
      </button>
      {confirming === 'skip' ? (
        <button
          onClick={() => handleClick('skip')}
          disabled={mutation.isPending}
          className="px-2 py-1 text-xs font-medium rounded border border-error/50 bg-error/20 text-error hover:bg-error/30 transition-colors disabled:opacity-50 animate-pulse"
        >
          Confirm
        </button>
      ) : (
        <button
          onClick={() => handleClick('skip')}
          disabled={mutation.isPending}
          className="px-2 py-1 text-xs font-medium rounded border border-error/30 bg-error/10 text-error hover:bg-error/20 transition-colors disabled:opacity-50"
        >
          Disqualify
        </button>
      )}
    </div>
  )
}
