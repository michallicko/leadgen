import { useState } from 'react'
import { useUpdateMessage } from '../../api/queries/useMessages'
import { useToast } from '../../components/ui/Toast'

const EDIT_REASONS = [
  { value: 'too_formal', label: 'Too formal' },
  { value: 'too_casual', label: 'Too casual' },
  { value: 'wrong_tone', label: 'Wrong tone' },
  { value: 'wrong_language', label: 'Wrong language' },
  { value: 'too_long', label: 'Too long' },
  { value: 'too_short', label: 'Too short' },
  { value: 'factually_wrong', label: 'Factually wrong' },
  { value: 'off_topic', label: 'Off topic' },
  { value: 'generic', label: 'Too generic' },
  { value: 'other', label: 'Other' },
]

interface EditPanelProps {
  messageId: string
  channel: string
  currentBody: string
  currentSubject: string | null
  onSave: () => void
  onCancel: () => void
}

export function EditPanel({ messageId, channel, currentBody, currentSubject, onSave, onCancel }: EditPanelProps) {
  const { toast } = useToast()
  const mutation = useUpdateMessage()
  const [body, setBody] = useState(currentBody)
  const [subject, setSubject] = useState(currentSubject ?? '')
  const [editReason, setEditReason] = useState('')
  const [editReasonText, setEditReasonText] = useState('')

  const hasChanges = body !== currentBody || (channel === 'email' && subject !== (currentSubject ?? ''))

  const handleSave = async () => {
    if (!hasChanges) {
      onCancel()
      return
    }
    if (!editReason) {
      toast('Please select an edit reason', 'error')
      return
    }

    const data: Record<string, unknown> = {
      body,
      edit_reason: editReason,
    }
    if (editReasonText) data.edit_reason_text = editReasonText
    if (channel === 'email' && subject !== (currentSubject ?? '')) {
      data.subject = subject
    }

    try {
      await mutation.mutateAsync({ id: messageId, data })
      toast('Edit saved', 'success')
      onSave()
    } catch {
      toast('Failed to save edit', 'error')
    }
  }

  return (
    <div className="space-y-4">
      {channel === 'email' && (
        <div>
          <label className="block text-xs font-medium text-text-muted mb-1">Subject</label>
          <input
            type="text"
            value={subject}
            onChange={e => setSubject(e.target.value)}
            className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
      )}

      <div>
        <label className="block text-xs font-medium text-text-muted mb-1">
          Body <span className="text-text-dim">({body.length} chars)</span>
        </label>
        <textarea
          value={body}
          onChange={e => setBody(e.target.value)}
          rows={8}
          className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-1 focus:ring-accent font-mono"
        />
      </div>

      {hasChanges && (
        <div className="space-y-2">
          <label className="block text-xs font-medium text-text-muted">Edit reason *</label>
          <select
            value={editReason}
            onChange={e => setEditReason(e.target.value)}
            className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="">Select reason...</option>
            {EDIT_REASONS.map(r => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>

          {editReason === 'other' && (
            <input
              type="text"
              placeholder="Describe the issue..."
              value={editReasonText}
              onChange={e => setEditReasonText(e.target.value)}
              className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-1 focus:ring-accent"
            />
          )}
        </div>
      )}

      <div className="flex gap-2 pt-2">
        <button
          onClick={handleSave}
          disabled={mutation.isPending || (hasChanges && !editReason)}
          className="px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {mutation.isPending ? 'Saving...' : 'Save Edit'}
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-2 bg-surface border border-border text-text text-sm rounded-lg hover:bg-surface-alt"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
