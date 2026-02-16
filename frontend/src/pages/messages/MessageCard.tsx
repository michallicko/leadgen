import { useState, useCallback } from 'react'
import { useUpdateMessage, type Message } from '../../api/queries/useMessages'
import { useToast } from '../../components/ui/Toast'

const REVIEW_BADGE_COLORS: Record<string, string> = {
  draft: 'bg-warning/15 text-warning border-warning/30',
  approved: 'bg-success/15 text-success border-success/30',
  rejected: 'bg-error/15 text-error border-error/30',
  sent: 'bg-[#00B8CF]/15 text-[#00B8CF] border-[#00B8CF]/30',
}

function ReviewBadge({ status }: { status: string }) {
  const colors = REVIEW_BADGE_COLORS[status] ?? 'bg-[#8B92A0]/10 text-text-muted border-[#8B92A0]/20'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border whitespace-nowrap ${colors}`}>
      {status}
    </span>
  )
}

const CHANNEL_LABELS: Record<string, string> = {
  linkedin_connect: 'LI Connect',
  linkedin_message: 'LI Message',
  email: 'Email',
  call_script: 'Call',
}

interface MessageCardProps {
  message: Message
}

export function MessageCard({ message }: MessageCardProps) {
  const { toast } = useToast()
  const mutation = useUpdateMessage()
  const [mode, setMode] = useState<'view' | 'edit' | 'reject'>('view')
  const [editBody, setEditBody] = useState(message.body)
  const [rejectNotes, setRejectNotes] = useState('')

  const handleApprove = useCallback(async () => {
    try {
      await mutation.mutateAsync({
        id: message.id,
        data: { status: 'approved', approved_at: new Date().toISOString() },
      })
      toast('Message approved', 'success')
    } catch {
      toast('Failed to approve', 'error')
    }
  }, [message.id, mutation, toast])

  const handleSaveEdit = useCallback(async () => {
    if (!editBody.trim()) {
      toast('Body cannot be empty', 'error')
      return
    }
    try {
      await mutation.mutateAsync({
        id: message.id,
        data: { body: editBody, status: 'approved', approved_at: new Date().toISOString() },
      })
      toast('Edited and approved', 'success')
      setMode('view')
    } catch {
      toast('Failed to save', 'error')
    }
  }, [message.id, editBody, mutation, toast])

  const handleReject = useCallback(async () => {
    try {
      await mutation.mutateAsync({
        id: message.id,
        data: { status: 'rejected', review_notes: rejectNotes || null },
      })
      toast('Message rejected', 'info')
      setMode('view')
      setRejectNotes('')
    } catch {
      toast('Failed to reject', 'error')
    }
  }, [message.id, rejectNotes, mutation, toast])

  const handleReset = useCallback(async () => {
    try {
      await mutation.mutateAsync({
        id: message.id,
        data: { status: 'draft', approved_at: null, review_notes: null },
      })
      toast('Reset to draft', 'info')
    } catch {
      toast('Failed to reset', 'error')
    }
  }, [message.id, mutation, toast])

  const isDraft = message.status === 'draft'
  const isApproved = message.status === 'approved'
  const isRejected = message.status === 'rejected'

  const opacity = isApproved ? 'opacity-60' : isRejected ? 'opacity-40' : ''
  const borderColor = isApproved
    ? 'border-success/30'
    : isRejected
      ? 'border-error/30'
      : 'border-border-solid'

  return (
    <div className={`rounded-lg border ${borderColor} bg-surface p-4 ${opacity} transition-opacity`}>
      {/* Card header */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className="text-xs font-medium text-text-muted">
          Step {message.sequence_step} · {message.variant}
        </span>
        <span className="text-xs px-1.5 py-0.5 rounded bg-surface-alt text-text-muted border border-border-solid">
          {CHANNEL_LABELS[message.channel] ?? message.channel}
        </span>
        <ReviewBadge status={message.status} />
        {message.tone && <span className="text-xs text-text-dim">{message.tone}</span>}
        {message.language && <span className="text-xs text-text-dim">{message.language}</span>}
        {message.generation_cost != null && (
          <span className="text-xs text-text-dim ml-auto">${message.generation_cost.toFixed(3)}</span>
        )}
      </div>

      {/* Subject (email only) */}
      {message.subject && (
        <div className="text-sm font-medium text-text mb-1">{message.subject}</div>
      )}

      {/* Body */}
      {mode === 'edit' ? (
        <div className="space-y-2">
          <textarea
            value={editBody}
            onChange={(e) => setEditBody(e.target.value)}
            rows={5}
            className="w-full bg-surface-alt border border-border-solid rounded-md px-3 py-2 text-sm text-text resize-y focus:outline-none focus:border-accent"
          />
          <div className="flex gap-2">
            <button
              onClick={handleSaveEdit}
              disabled={mutation.isPending}
              className="px-3 py-1.5 text-xs bg-accent hover:bg-accent-hover text-white rounded-md disabled:opacity-50"
            >
              Save & Approve
            </button>
            <button
              onClick={() => { setMode('view'); setEditBody(message.body) }}
              className="px-3 py-1.5 text-xs text-text-muted hover:text-text"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : mode === 'reject' ? (
        <div className="space-y-2">
          <div className="text-sm text-text whitespace-pre-wrap">{message.body}</div>
          <textarea
            value={rejectNotes}
            onChange={(e) => setRejectNotes(e.target.value)}
            rows={2}
            placeholder="Rejection reason (optional)"
            className="w-full bg-surface-alt border border-border-solid rounded-md px-3 py-2 text-sm text-text resize-y focus:outline-none focus:border-accent"
          />
          <div className="flex gap-2">
            <button
              onClick={handleReject}
              disabled={mutation.isPending}
              className="px-3 py-1.5 text-xs bg-error/20 text-error hover:bg-error/30 rounded-md border border-error/30 disabled:opacity-50"
            >
              Confirm Reject
            </button>
            <button
              onClick={() => { setMode('view'); setRejectNotes('') }}
              className="px-3 py-1.5 text-xs text-text-muted hover:text-text"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="text-sm text-text whitespace-pre-wrap">{message.body}</div>
      )}

      {/* Review notes (shown when approved/rejected) */}
      {mode === 'view' && message.review_notes && (
        <div className="mt-2 text-xs text-text-dim italic">
          Note: {message.review_notes}
        </div>
      )}

      {/* Actions */}
      {mode === 'view' && (
        <div className="flex items-center gap-2 mt-3 pt-2 border-t border-border/50">
          {isDraft && (
            <>
              <button onClick={handleApprove} disabled={mutation.isPending} className="px-2.5 py-1 text-xs text-success hover:bg-success/10 rounded transition-colors">Approve</button>
              <button onClick={() => setMode('edit')} className="px-2.5 py-1 text-xs text-accent-cyan hover:bg-accent/10 rounded transition-colors">Edit</button>
              <button onClick={() => setMode('reject')} className="px-2.5 py-1 text-xs text-error hover:bg-error/10 rounded transition-colors">Reject</button>
            </>
          )}
          {(isApproved || isRejected) && (
            <button onClick={handleReset} disabled={mutation.isPending} className="px-2.5 py-1 text-xs text-text-muted hover:text-text hover:bg-surface-alt rounded transition-colors">Reset to Draft</button>
          )}
        </div>
      )}
    </div>
  )
}
