import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router'
import {
  useReviewQueue, useUpdateMessage,
  type ReviewQueueItem,
} from '../../api/queries/useMessages'
import { useToast } from '../../components/ui/Toast'
import { EditPanel } from './EditPanel'
import { RegenerationDialog } from './RegenerationDialog'
import { DisqualifyDialog } from './DisqualifyDialog'

const CHANNEL_LABELS: Record<string, string> = {
  linkedin_connect: 'LI Connect',
  linkedin_message: 'LI Message',
  email: 'Email',
  call_script: 'Call',
}

export function MessageReviewPage() {
  const { campaignId } = useParams<{ campaignId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { toast } = useToast()

  const statusFilter = searchParams.get('status') ?? 'draft'
  const channelFilter = searchParams.get('channel') ?? undefined
  const stepFilter = searchParams.get('step') ?? undefined

  const { data, isLoading, refetch } = useReviewQueue(
    campaignId ?? null,
    { status: statusFilter, channel: channelFilter, step: stepFilter },
  )
  const updateMutation = useUpdateMessage()

  const [currentIndex, setCurrentIndex] = useState(0)
  const [mode, setMode] = useState<'view' | 'edit' | 'reject'>('view')
  const [rejectNotes, setRejectNotes] = useState('')
  const [showRegenDialog, setShowRegenDialog] = useState(false)
  const [showDisqualifyDialog, setShowDisqualifyDialog] = useState(false)

  const queue = data?.queue ?? []
  const stats = data?.stats
  const current = queue[currentIndex] as ReviewQueueItem | undefined
  const isComplete = queue.length === 0 && !isLoading

  // Find how many messages remain for current contact to skip on disqualify
  const contactMessageCount = useMemo(() => {
    if (!current) return 0
    let count = 0
    for (let i = currentIndex; i < queue.length; i++) {
      if (queue[i].contact.id === current.contact.id) count++
      else break
    }
    return count
  }, [queue, currentIndex, current])

  const advance = useCallback(() => {
    setMode('view')
    setRejectNotes('')
    if (currentIndex < queue.length - 1) {
      setCurrentIndex(i => i + 1)
    } else {
      // Queue exhausted — refetch to check for more
      refetch()
    }
  }, [currentIndex, queue.length, refetch])

  const handleApprove = useCallback(async () => {
    if (!current) return
    try {
      await updateMutation.mutateAsync({
        id: current.message.id,
        data: { status: 'approved', approved_at: new Date().toISOString() },
      })
      toast('Approved', 'success')
      advance()
    } catch {
      toast('Failed to approve', 'error')
    }
  }, [current, updateMutation, toast, advance])

  const handleReject = useCallback(async () => {
    if (!current || !rejectNotes.trim()) {
      toast('Please enter a rejection reason', 'error')
      return
    }
    try {
      await updateMutation.mutateAsync({
        id: current.message.id,
        data: { status: 'rejected', review_notes: rejectNotes.trim() },
      })
      toast('Rejected', 'success')
      advance()
    } catch {
      toast('Failed to reject', 'error')
    }
  }, [current, rejectNotes, updateMutation, toast, advance])

  const handleEditSaved = useCallback(() => {
    setMode('view')
    refetch()
  }, [refetch])

  const handleRegenerated = useCallback(() => {
    setShowRegenDialog(false)
    refetch()
  }, [refetch])

  const handleDisqualified = useCallback((scope: 'campaign' | 'global') => {
    setShowDisqualifyDialog(false)
    // Skip past remaining messages for this contact
    if (scope === 'campaign' || scope === 'global') {
      const skip = contactMessageCount
      if (currentIndex + skip < queue.length) {
        setCurrentIndex(i => i + skip)
      } else {
        refetch()
      }
    }
  }, [contactMessageCount, currentIndex, queue.length, refetch])

  // Keyboard shortcuts (T15)
  useEffect(() => {
    if (mode !== 'view' || showRegenDialog || showDisqualifyDialog) return

    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      switch (e.key.toLowerCase()) {
        case 'a':
          e.preventDefault()
          handleApprove()
          break
        case 'r':
          e.preventDefault()
          setMode('reject')
          break
        case 'e':
          e.preventDefault()
          setMode('edit')
          break
        case 'g':
          e.preventDefault()
          setShowRegenDialog(true)
          break
        case 'd':
          e.preventDefault()
          setShowDisqualifyDialog(true)
          break
        case 'escape':
          navigate(-1)
          break
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [mode, showRegenDialog, showDisqualifyDialog, handleApprove, navigate])

  // Handle Escape in reject mode
  useEffect(() => {
    if (mode !== 'reject') return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setMode('view')
        setRejectNotes('')
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [mode])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin w-8 h-8 border-2 border-accent border-t-transparent rounded-full" />
      </div>
    )
  }

  // Completion state
  if (isComplete) {
    return (
      <div className="max-w-lg mx-auto mt-20 text-center">
        <div className="text-4xl mb-4">&#10003;</div>
        <h2 className="text-xl font-semibold text-text mb-2">Review Complete</h2>
        {stats && (
          <div className="text-sm text-text-muted mb-6 space-y-1">
            <div>{stats.approved} approved / {stats.rejected} rejected / {stats.draft} remaining</div>
            <div>Total: {stats.total} messages</div>
          </div>
        )}
        <button
          onClick={() => navigate(-1)}
          className="px-6 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent-hover"
        >
          Back to Campaign
        </button>
      </div>
    )
  }

  if (!current) return null

  const { message: msg, contact, company } = current

  return (
    <div className="max-w-5xl mx-auto">
      {/* Progress bar */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate(-1)} className="text-text-muted hover:text-text text-sm">
          &larr; Back
        </button>
        <div className="flex-1 bg-surface-alt rounded-full h-2 overflow-hidden">
          <div
            className="bg-accent h-full transition-all duration-300"
            style={{ width: `${((currentIndex + 1) / queue.length) * 100}%` }}
          />
        </div>
        <span className="text-sm text-text-muted whitespace-nowrap">
          {currentIndex + 1} of {queue.length}
        </span>
        {stats && (
          <span className="text-xs text-text-dim">
            ({stats.approved} approved, {stats.rejected} rejected)
          </span>
        )}
      </div>

      <div className="grid grid-cols-[1fr_2fr] gap-6">
        {/* Left: Contact + Company context */}
        <div className="space-y-4">
          {/* Contact card */}
          <div className="bg-surface border border-border rounded-xl p-4">
            <h3 className="text-sm font-semibold text-text mb-2">{contact.full_name}</h3>
            {contact.job_title && <div className="text-xs text-text-muted">{contact.job_title}</div>}
            <div className="mt-3 space-y-1.5 text-xs text-text-muted">
              {contact.email_address && <div>&#9993; {contact.email_address}</div>}
              {contact.linkedin_url && (
                <div>
                  <a href={contact.linkedin_url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                    LinkedIn
                  </a>
                </div>
              )}
              {contact.seniority_level && <div>Seniority: {contact.seniority_level}</div>}
              {contact.department && <div>Dept: {contact.department}</div>}
            </div>
            <div className="mt-3 flex gap-2 flex-wrap">
              {contact.icp_fit && (
                <span className="text-[10px] px-1.5 py-0.5 bg-accent/10 text-accent rounded">
                  ICP: {contact.icp_fit}
                </span>
              )}
              {contact.contact_score != null && (
                <span className="text-[10px] px-1.5 py-0.5 bg-[#00B8CF]/10 text-[#00B8CF] rounded">
                  Score: {contact.contact_score}
                </span>
              )}
            </div>
          </div>

          {/* Company card */}
          {company && (
            <div className="bg-surface border border-border rounded-xl p-4">
              <h3 className="text-sm font-semibold text-text mb-1">{company.name}</h3>
              {company.domain && <div className="text-xs text-text-dim mb-2">{company.domain}</div>}
              <div className="space-y-1.5 text-xs text-text-muted">
                {company.tier && <div>Tier: {company.tier}</div>}
                {company.industry && <div>Industry: {company.industry}</div>}
                {company.hq_country && <div>Country: {company.hq_country}</div>}
                {company.summary && (
                  <div className="mt-2 text-text-dim leading-relaxed line-clamp-4">{company.summary}</div>
                )}
              </div>
            </div>
          )}

          {/* Keyboard shortcuts */}
          <div className="bg-surface border border-border rounded-xl p-3">
            <div className="text-[10px] font-medium text-text-dim uppercase tracking-wide mb-2">Shortcuts</div>
            <div className="grid grid-cols-2 gap-1 text-xs text-text-muted">
              <div><kbd className="px-1 py-0.5 bg-surface-alt rounded text-[10px]">A</kbd> Approve</div>
              <div><kbd className="px-1 py-0.5 bg-surface-alt rounded text-[10px]">R</kbd> Reject</div>
              <div><kbd className="px-1 py-0.5 bg-surface-alt rounded text-[10px]">E</kbd> Edit</div>
              <div><kbd className="px-1 py-0.5 bg-surface-alt rounded text-[10px]">G</kbd> Regenerate</div>
              <div><kbd className="px-1 py-0.5 bg-surface-alt rounded text-[10px]">D</kbd> Disqualify</div>
              <div><kbd className="px-1 py-0.5 bg-surface-alt rounded text-[10px]">Esc</kbd> Back</div>
            </div>
          </div>
        </div>

        {/* Right: Message content + actions */}
        <div className="bg-surface border border-border rounded-xl p-6">
          {/* Message header */}
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xs px-2 py-0.5 bg-accent/10 text-accent rounded font-medium">
              {CHANNEL_LABELS[msg.channel] ?? msg.channel}
            </span>
            {msg.label && <span className="text-xs text-text-muted">{msg.label}</span>}
            <span className="text-xs text-text-dim">Step {msg.sequence_step}</span>
            {msg.tone && <span className="text-xs text-text-dim capitalize">{msg.tone}</span>}
            {msg.language && <span className="text-xs text-text-dim uppercase">{msg.language}</span>}
            {msg.regen_count > 0 && (
              <span className="text-[10px] px-1.5 py-0.5 bg-warning/15 text-warning rounded">
                regen x{msg.regen_count}
              </span>
            )}
          </div>

          {/* Message body */}
          {mode === 'edit' ? (
            <EditPanel
              messageId={msg.id}
              channel={msg.channel}
              currentBody={msg.body}
              currentSubject={msg.subject}
              onSave={handleEditSaved}
              onCancel={() => setMode('view')}
            />
          ) : (
            <>
              {msg.channel === 'email' && msg.subject && (
                <div className="mb-3">
                  <span className="text-xs text-text-dim">Subject:</span>
                  <div className="text-sm font-medium text-text">{msg.subject}</div>
                </div>
              )}

              <div className="whitespace-pre-wrap text-sm text-text leading-relaxed mb-4">
                {msg.body}
              </div>

              {msg.original_body && msg.original_body !== msg.body && (
                <details className="mb-4">
                  <summary className="text-xs text-text-dim cursor-pointer hover:text-text-muted">
                    Show original
                  </summary>
                  <div className="mt-2 p-3 bg-surface-alt rounded-lg text-xs text-text-muted whitespace-pre-wrap">
                    {msg.original_body}
                  </div>
                </details>
              )}

              {/* Reject mode */}
              {mode === 'reject' && (
                <div className="mb-4 p-3 bg-error/5 border border-error/20 rounded-lg">
                  <label className="block text-xs font-medium text-error mb-1">Rejection reason *</label>
                  <textarea
                    autoFocus
                    value={rejectNotes}
                    onChange={e => setRejectNotes(e.target.value)}
                    placeholder="Why is this message being rejected?"
                    rows={2}
                    className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-1 focus:ring-error"
                  />
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={handleReject}
                      disabled={!rejectNotes.trim() || updateMutation.isPending}
                      className="px-3 py-1.5 bg-error text-white text-xs font-medium rounded-lg hover:bg-error/90 disabled:opacity-50"
                    >
                      Confirm Reject
                    </button>
                    <button
                      onClick={() => { setMode('view'); setRejectNotes('') }}
                      className="px-3 py-1.5 bg-surface border border-border text-text text-xs rounded-lg hover:bg-surface-alt"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Action buttons */}
              {mode === 'view' && (
                <div className="flex gap-2 flex-wrap">
                  <button
                    onClick={handleApprove}
                    disabled={updateMutation.isPending}
                    className="px-4 py-2 bg-success text-white text-sm font-medium rounded-lg hover:bg-success/90 disabled:opacity-50"
                    title="Approve (A)"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => setMode('reject')}
                    className="px-4 py-2 bg-error/10 text-error text-sm font-medium rounded-lg border border-error/20 hover:bg-error/20"
                    title="Reject (R)"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => setMode('edit')}
                    className="px-4 py-2 bg-surface border border-border text-text text-sm rounded-lg hover:bg-surface-alt"
                    title="Edit (E)"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => setShowRegenDialog(true)}
                    className="px-4 py-2 bg-surface border border-border text-text text-sm rounded-lg hover:bg-surface-alt"
                    title="Regenerate (G)"
                  >
                    Regenerate
                  </button>
                  <button
                    onClick={() => setShowDisqualifyDialog(true)}
                    className="px-4 py-2 bg-surface border border-border text-error/80 text-sm rounded-lg hover:bg-error/5"
                    title="Disqualify (D)"
                  >
                    Disqualify
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Dialogs */}
      {showRegenDialog && current && (
        <RegenerationDialog
          messageId={msg.id}
          currentLanguage={msg.language}
          currentTone={msg.tone}
          onClose={() => setShowRegenDialog(false)}
          onRegenerated={handleRegenerated}
        />
      )}

      {showDisqualifyDialog && current && (
        <DisqualifyDialog
          campaignId={campaignId!}
          contactId={contact.id}
          contactName={contact.full_name}
          onClose={() => setShowDisqualifyDialog(false)}
          onDisqualified={handleDisqualified}
        />
      )}
    </div>
  )
}
