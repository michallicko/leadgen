import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import {
  useReviewQueue,
  useUpdateMessage,
  useRegenerateMessage,
  type ReviewQueueItem,
} from '../../api/queries/useMessages'
import { useToast } from '../ui/Toast'

// ── Constants ──────────────────────────────────────────

const CHANNEL_LABELS: Record<string, string> = {
  linkedin_connect: 'LI Connect',
  linkedin_message: 'LI Message',
  email: 'Email',
  call_script: 'Call',
}

const CHANNEL_BADGE_COLORS: Record<string, string> = {
  email: 'bg-[#00B8CF]/15 text-[#00B8CF] border-[#00B8CF]/30',
  linkedin_connect: 'bg-accent/15 text-accent-hover border-accent/30',
  linkedin_message: 'bg-accent/15 text-accent-hover border-accent/30',
  call_script: 'bg-warning/15 text-warning border-warning/30',
}

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

// ── Types ──────────────────────────────────────────────

type ReviewMode = 'view' | 'edit' | 'reject'

interface MessageReviewQueueProps {
  campaignId: string
  initialFilter?: 'all' | 'draft' | 'rejected'
  onClose: () => void
}

// ── Component ──────────────────────────────────────────

export function MessageReviewQueue({ campaignId, initialFilter, onClose }: MessageReviewQueueProps) {
  const { toast } = useToast()

  // Fetch the review queue
  const statusFilter = initialFilter === 'all' ? undefined : (initialFilter ?? 'draft')
  const { data, isLoading, refetch } = useReviewQueue(campaignId, { status: statusFilter })
  const updateMutation = useUpdateMessage()
  const regenMutation = useRegenerateMessage()

  // Navigation state
  const [currentIndex, setCurrentIndex] = useState(0)
  const [mode, setMode] = useState<ReviewMode>('view')
  const [rejectNotes, setRejectNotes] = useState('')
  const [contextOpen, setContextOpen] = useState(true)

  // Edit state
  const [editBody, setEditBody] = useState('')
  const [editSubject, setEditSubject] = useState('')
  const [editReason, setEditReason] = useState('')

  // Regen state
  const [isRegenerating, setIsRegenerating] = useState(false)

  // Transition state
  const [slideDirection, setSlideDirection] = useState<'left' | 'right' | null>(null)
  const contentRef = useRef<HTMLDivElement>(null)

  // Track completed actions
  const [actionCounts, setActionCounts] = useState({ approved: 0, rejected: 0, edited: 0, skipped: 0 })

  const queue = data?.queue ?? []
  const stats = data?.stats
  const current = queue[currentIndex] as ReviewQueueItem | undefined
  const isComplete = queue.length === 0 && !isLoading

  // Reset edit state when current message changes
  useEffect(() => {
    if (current) {
      setEditBody(current.message.body)
      setEditSubject(current.message.subject ?? '')
      setMode('view')
      setRejectNotes('')
      setEditReason('')
    }
  }, [current])

  // Lock body scroll while overlay is open
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  // Animate slide transition
  const animateTransition = useCallback((direction: 'left' | 'right') => {
    setSlideDirection(direction)
    const timer = setTimeout(() => setSlideDirection(null), 200)
    return () => clearTimeout(timer)
  }, [])

  const advance = useCallback(() => {
    setMode('view')
    setRejectNotes('')
    setEditReason('')
    if (currentIndex < queue.length - 1) {
      animateTransition('left')
      setCurrentIndex(i => i + 1)
    } else {
      // Queue exhausted -- refetch to check for more
      refetch()
    }
  }, [currentIndex, queue.length, refetch, animateTransition])

  const goBack = useCallback(() => {
    if (currentIndex > 0) {
      animateTransition('right')
      setCurrentIndex(i => i - 1)
      setMode('view')
      setRejectNotes('')
      setEditReason('')
    }
  }, [currentIndex, animateTransition])

  // ── Actions ──────────────────────────────────────────

  const handleApprove = useCallback(async () => {
    if (!current) return
    try {
      await updateMutation.mutateAsync({
        id: current.message.id,
        data: { status: 'approved', approved_at: new Date().toISOString() },
      })
      setActionCounts(c => ({ ...c, approved: c.approved + 1 }))
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
      setActionCounts(c => ({ ...c, rejected: c.rejected + 1 }))
      toast('Rejected', 'success')
      advance()
    } catch {
      toast('Failed to reject', 'error')
    }
  }, [current, rejectNotes, updateMutation, toast, advance])

  const handleEditSave = useCallback(async () => {
    if (!current) return
    const hasChanges = editBody !== current.message.body ||
      (current.message.channel === 'email' && editSubject !== (current.message.subject ?? ''))

    if (hasChanges && !editReason) {
      toast('Please select an edit reason', 'error')
      return
    }

    const payload: Record<string, unknown> = {
      status: 'approved',
      approved_at: new Date().toISOString(),
    }
    if (editBody !== current.message.body) {
      payload.body = editBody
      payload.edit_reason = editReason
    }
    if (current.message.channel === 'email' && editSubject !== (current.message.subject ?? '')) {
      payload.subject = editSubject
    }

    try {
      await updateMutation.mutateAsync({ id: current.message.id, data: payload })
      setActionCounts(c => ({ ...c, edited: c.edited + 1 }))
      toast(hasChanges ? 'Edited and approved' : 'Approved', 'success')
      advance()
    } catch {
      toast('Failed to save edit', 'error')
    }
  }, [current, editBody, editSubject, editReason, updateMutation, toast, advance])

  const handleRegenerate = useCallback(async () => {
    if (!current) return
    setIsRegenerating(true)
    try {
      await regenMutation.mutateAsync({
        id: current.message.id,
        data: {},
      })
      toast('Message regenerated', 'success')
      refetch()
    } catch {
      toast('Regeneration failed', 'error')
    } finally {
      setIsRegenerating(false)
    }
  }, [current, regenMutation, toast, refetch])

  const handleSkip = useCallback(() => {
    setActionCounts(c => ({ ...c, skipped: c.skipped + 1 }))
    advance()
  }, [advance])

  // ── Keyboard shortcuts ───────────────────────────────

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') {
        // Allow Escape in form elements to cancel the mode
        if (e.key === 'Escape') {
          e.preventDefault()
          if (mode === 'reject') {
            setMode('view')
            setRejectNotes('')
          } else if (mode === 'edit') {
            setMode('view')
            if (current) {
              setEditBody(current.message.body)
              setEditSubject(current.message.subject ?? '')
            }
            setEditReason('')
          }
        }
        // Cmd/Ctrl+Enter to save edit
        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && mode === 'edit') {
          e.preventDefault()
          handleEditSave()
        }
        // Enter in reject mode confirms rejection
        if (e.key === 'Enter' && !e.shiftKey && mode === 'reject') {
          e.preventDefault()
          handleReject()
        }
        return
      }

      if (isRegenerating) return

      switch (e.key) {
        case 'a':
        case 'ArrowRight':
          if (mode === 'view') {
            e.preventDefault()
            handleApprove()
          }
          break
        case 'r':
          if (mode === 'view') {
            e.preventDefault()
            setMode('reject')
          }
          break
        case 'e':
          if (mode === 'view') {
            e.preventDefault()
            setMode('edit')
          }
          break
        case 'g':
          if (mode === 'view') {
            e.preventDefault()
            handleRegenerate()
          }
          break
        case 'ArrowLeft':
          if (mode === 'view') {
            e.preventDefault()
            goBack()
          }
          break
        case 'Escape':
          e.preventDefault()
          if (mode !== 'view') {
            setMode('view')
            setRejectNotes('')
            setEditReason('')
          } else {
            onClose()
          }
          break
        case 'n':
          if (mode === 'view') {
            e.preventDefault()
            handleSkip()
          }
          break
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [mode, current, isRegenerating, handleApprove, handleReject, handleEditSave, handleRegenerate, handleSkip, goBack, onClose])

  // ── Progress summary ─────────────────────────────────

  const progressText = useMemo(() => {
    if (!queue.length) return ''
    const parts: string[] = []
    if (actionCounts.approved > 0) parts.push(`${actionCounts.approved} approved`)
    if (actionCounts.rejected > 0) parts.push(`${actionCounts.rejected} rejected`)
    if (actionCounts.edited > 0) parts.push(`${actionCounts.edited} edited`)
    if (actionCounts.skipped > 0) parts.push(`${actionCounts.skipped} skipped`)
    return parts.length > 0 ? parts.join(', ') : ''
  }, [queue.length, actionCounts])

  // ── Render ───────────────────────────────────────────

  // Loading state
  if (isLoading) {
    return (
      <div className="fixed inset-0 z-50 bg-bg flex items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border-2 border-border border-t-accent rounded-full animate-spin mx-auto mb-4" />
          <div className="text-sm text-text-muted">Loading review queue...</div>
        </div>
      </div>
    )
  }

  // Completion state
  if (isComplete) {
    return (
      <div className="fixed inset-0 z-50 bg-bg flex items-center justify-center">
        <div className="max-w-md text-center">
          <div className="w-16 h-16 bg-success/15 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-success">
              <path d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-2xl font-semibold text-text mb-3">Review Complete</h2>
          {stats && (
            <div className="text-sm text-text-muted mb-2 space-y-1">
              <div>{stats.total} total messages</div>
              <div className="flex items-center justify-center gap-4 text-xs mt-2">
                <span className="text-success">{stats.approved} approved</span>
                <span className="text-error">{stats.rejected} rejected</span>
                <span className="text-text-dim">{stats.draft} remaining</span>
              </div>
            </div>
          )}
          {progressText && (
            <div className="text-xs text-text-dim mt-3 mb-6">
              This session: {progressText}
            </div>
          )}
          <button
            onClick={onClose}
            className="px-6 py-2.5 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent-hover transition-colors"
          >
            Back to Messages
          </button>
        </div>
      </div>
    )
  }

  if (!current) return null

  const { message: msg, contact, company } = current
  const channelLabel = CHANNEL_LABELS[msg.channel] ?? msg.channel
  const channelColors = CHANNEL_BADGE_COLORS[msg.channel] ?? CHANNEL_BADGE_COLORS.email

  const slideClass = slideDirection === 'left'
    ? 'animate-slide-left'
    : slideDirection === 'right'
      ? 'animate-slide-right'
      : ''

  return (
    <div className="fixed inset-0 z-50 bg-bg flex flex-col">
      {/* ── Top bar: progress ─────────────────────────── */}
      <div className="flex items-center gap-3 px-6 py-3 border-b border-border-solid bg-surface">
        <button
          onClick={onClose}
          className="flex items-center gap-1.5 text-sm text-text-muted hover:text-text transition-colors bg-transparent border-none cursor-pointer p-0"
          title="Exit review (Esc)"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M10 4l-4 4 4 4" />
          </svg>
          Exit
        </button>

        <div className="flex-1 flex items-center gap-3">
          <div className="flex-1 bg-surface-alt rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-accent h-full transition-all duration-300 ease-out"
              style={{ width: `${((currentIndex + 1) / queue.length) * 100}%` }}
            />
          </div>
          <span className="text-sm text-text whitespace-nowrap font-medium">
            {currentIndex + 1} of {queue.length}
          </span>
        </div>

        {progressText && (
          <span className="text-xs text-text-dim ml-2">
            {progressText}
          </span>
        )}
      </div>

      {/* ── Main content ──────────────────────────────── */}
      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* Left panel: Contact + Company context */}
        <div
          className={`border-r border-border-solid bg-surface transition-all duration-200 overflow-y-auto ${
            contextOpen ? 'w-80 min-w-[320px]' : 'w-0 min-w-0 overflow-hidden'
          }`}
        >
          {contextOpen && (
            <div className="p-5 space-y-4">
              {/* Contact card */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs font-medium text-text-dim uppercase tracking-wider">Contact</h3>
                  <button
                    onClick={() => setContextOpen(false)}
                    className="p-1 rounded text-text-dim hover:text-text hover:bg-surface-alt transition-colors bg-transparent border-none cursor-pointer"
                    title="Hide context panel"
                  >
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M9 3l-4 4 4 4" />
                    </svg>
                  </button>
                </div>

                <div className="bg-surface-alt/50 border border-border rounded-lg p-4 space-y-2">
                  <div className="text-sm font-semibold text-text">{contact.full_name}</div>
                  {contact.job_title && (
                    <div className="text-xs text-text-muted">{contact.job_title}</div>
                  )}

                  <div className="pt-2 space-y-1.5 text-xs text-text-muted">
                    {contact.email_address && (
                      <div className="flex items-center gap-1.5">
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <rect x="1" y="2.5" width="10" height="7" rx="1" />
                          <path d="M1 3.5l5 3 5-3" />
                        </svg>
                        {contact.email_address}
                      </div>
                    )}
                    {contact.linkedin_url && (
                      <div className="flex items-center gap-1.5">
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M4 8V5M8 8V6.5a1.5 1.5 0 10-3 0M4 3.5v.01" />
                        </svg>
                        <a href={contact.linkedin_url} target="_blank" rel="noreferrer" className="text-accent hover:underline truncate">
                          LinkedIn Profile
                        </a>
                      </div>
                    )}
                    {contact.seniority_level && <div>Seniority: {contact.seniority_level}</div>}
                    {contact.department && <div>Dept: {contact.department}</div>}
                    {contact.location_country && <div>Location: {contact.location_country}</div>}
                  </div>

                  {/* Tags */}
                  <div className="flex gap-1.5 flex-wrap pt-2">
                    {contact.icp_fit && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-accent/10 text-accent rounded font-medium">
                        ICP: {contact.icp_fit}
                      </span>
                    )}
                    {contact.contact_score != null && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-[#00B8CF]/10 text-[#00B8CF] rounded font-medium">
                        Score: {contact.contact_score}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Company card */}
              {company && (
                <div>
                  <h3 className="text-xs font-medium text-text-dim uppercase tracking-wider mb-3">Company</h3>
                  <div className="bg-surface-alt/50 border border-border rounded-lg p-4 space-y-2">
                    <div className="text-sm font-semibold text-text">{company.name}</div>
                    {company.domain && (
                      <div className="text-xs text-text-dim">{company.domain}</div>
                    )}

                    <div className="pt-1 space-y-1.5 text-xs text-text-muted">
                      {company.tier && <div>Tier: <span className="text-text">{company.tier}</span></div>}
                      {company.industry && <div>Industry: {company.industry}</div>}
                      {company.hq_country && <div>HQ: {company.hq_country}</div>}
                    </div>

                    {company.summary && (
                      <details className="pt-2">
                        <summary className="text-xs text-text-dim cursor-pointer hover:text-text-muted">
                          Company summary
                        </summary>
                        <div className="mt-2 text-xs text-text-muted leading-relaxed">
                          {company.summary}
                        </div>
                      </details>
                    )}
                  </div>
                </div>
              )}

              {/* Shortcuts reference */}
              <div>
                <h3 className="text-xs font-medium text-text-dim uppercase tracking-wider mb-3">Keyboard Shortcuts</h3>
                <div className="bg-surface-alt/50 border border-border rounded-lg p-3">
                  <div className="grid grid-cols-2 gap-y-1.5 gap-x-3 text-xs">
                    <div className="flex items-center gap-1.5">
                      <kbd className="px-1.5 py-0.5 bg-surface rounded text-[10px] font-mono border border-border-solid min-w-[20px] text-center">A</kbd>
                      <span className="text-text-muted">Approve</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <kbd className="px-1.5 py-0.5 bg-surface rounded text-[10px] font-mono border border-border-solid min-w-[20px] text-center">R</kbd>
                      <span className="text-text-muted">Reject</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <kbd className="px-1.5 py-0.5 bg-surface rounded text-[10px] font-mono border border-border-solid min-w-[20px] text-center">E</kbd>
                      <span className="text-text-muted">Edit</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <kbd className="px-1.5 py-0.5 bg-surface rounded text-[10px] font-mono border border-border-solid min-w-[20px] text-center">G</kbd>
                      <span className="text-text-muted">Regenerate</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <kbd className="px-1.5 py-0.5 bg-surface rounded text-[10px] font-mono border border-border-solid min-w-[20px] text-center">N</kbd>
                      <span className="text-text-muted">Skip/Next</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <kbd className="px-1.5 py-0.5 bg-surface rounded text-[10px] font-mono border border-border-solid text-[9px]">&larr;</kbd>
                      <span className="text-text-muted">Go back</span>
                    </div>
                    <div className="flex items-center gap-1.5 col-span-2">
                      <kbd className="px-1.5 py-0.5 bg-surface rounded text-[10px] font-mono border border-border-solid">Esc</kbd>
                      <span className="text-text-muted">Exit review</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Expand button when context is collapsed */}
        {!contextOpen && (
          <button
            onClick={() => setContextOpen(true)}
            className="w-8 flex-shrink-0 flex items-center justify-center border-r border-border-solid bg-surface hover:bg-surface-alt transition-colors cursor-pointer border-none"
            title="Show context panel"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-text-dim">
              <path d="M5 3l4 4-4 4" />
            </svg>
          </button>
        )}

        {/* Right panel: Message content */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <div
            ref={contentRef}
            className={`flex-1 overflow-y-auto px-8 py-6 ${slideClass}`}
          >
            <div className="max-w-2xl mx-auto">
              {/* Message header */}
              <div className="flex items-center gap-2 mb-5 flex-wrap">
                <span className={`inline-flex items-center px-2.5 py-1 text-xs font-medium rounded border ${channelColors}`}>
                  {channelLabel}
                </span>
                {msg.label && (
                  <span className="text-xs text-text-muted">{msg.label}</span>
                )}
                <span className="text-xs text-text-dim">Step {msg.sequence_step}</span>
                {msg.variant && (
                  <span className="text-xs text-text-dim">Variant {msg.variant}</span>
                )}
                {msg.tone && (
                  <span className="text-xs text-text-dim capitalize">{msg.tone}</span>
                )}
                {msg.language && (
                  <span className="text-xs text-text-dim uppercase">{msg.language}</span>
                )}
                {msg.regen_count > 0 && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-warning/15 text-warning rounded font-medium">
                    regen x{msg.regen_count}
                  </span>
                )}
                {msg.generation_cost != null && (
                  <span className="text-xs text-text-dim ml-auto">${msg.generation_cost.toFixed(3)}</span>
                )}
              </div>

              {/* ── View mode ─────────────────────────── */}
              {mode === 'view' && (
                <>
                  {/* Subject (email only) */}
                  {msg.channel === 'email' && msg.subject && (
                    <div className="mb-4">
                      <span className="text-xs text-text-dim block mb-1">Subject</span>
                      <div className="text-base font-medium text-text">{msg.subject}</div>
                    </div>
                  )}

                  {/* Body */}
                  <div className="bg-surface-alt/30 border border-border rounded-lg p-5">
                    <div className="whitespace-pre-wrap text-sm text-text leading-relaxed">
                      {msg.body}
                    </div>
                  </div>

                  {/* Original (if edited previously) */}
                  {msg.original_body && msg.original_body !== msg.body && (
                    <details className="mt-4">
                      <summary className="text-xs text-text-dim cursor-pointer hover:text-text-muted">
                        Show original version
                      </summary>
                      <div className="mt-2 p-4 bg-surface-alt/50 rounded-lg text-xs text-text-muted whitespace-pre-wrap border border-border/50">
                        {msg.original_body}
                      </div>
                    </details>
                  )}

                  {/* Regenerating indicator */}
                  {isRegenerating && (
                    <div className="mt-4 flex items-center gap-2 text-sm text-text-muted">
                      <div className="w-4 h-4 border-2 border-border border-t-accent rounded-full animate-spin" />
                      Regenerating message...
                    </div>
                  )}
                </>
              )}

              {/* ── Edit mode ─────────────────────────── */}
              {mode === 'edit' && (
                <div className="space-y-4">
                  {msg.channel === 'email' && (
                    <div>
                      <label className="block text-xs font-medium text-text-muted mb-1">Subject</label>
                      <input
                        type="text"
                        value={editSubject}
                        onChange={e => setEditSubject(e.target.value)}
                        className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-1 focus:ring-accent"
                      />
                    </div>
                  )}

                  <div>
                    <label className="block text-xs font-medium text-text-muted mb-1">
                      Body <span className="text-text-dim">({editBody.length} chars)</span>
                    </label>
                    <textarea
                      autoFocus
                      value={editBody}
                      onChange={e => setEditBody(e.target.value)}
                      rows={10}
                      className="w-full px-4 py-3 bg-surface border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-1 focus:ring-accent font-mono leading-relaxed"
                    />
                  </div>

                  {/* Edit reason (only if body changed) */}
                  {(editBody !== current.message.body || (msg.channel === 'email' && editSubject !== (msg.subject ?? ''))) && (
                    <div>
                      <label className="block text-xs font-medium text-text-muted mb-1">Edit reason *</label>
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
                    </div>
                  )}

                  <div className="flex gap-2 pt-2">
                    <button
                      onClick={handleEditSave}
                      disabled={updateMutation.isPending}
                      className="px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent-hover disabled:opacity-50 transition-colors"
                    >
                      {updateMutation.isPending ? 'Saving...' : 'Save & Approve'}
                    </button>
                    <button
                      onClick={() => {
                        setMode('view')
                        setEditBody(current.message.body)
                        setEditSubject(current.message.subject ?? '')
                        setEditReason('')
                      }}
                      className="px-4 py-2 bg-surface border border-border text-text text-sm rounded-lg hover:bg-surface-alt transition-colors"
                    >
                      Cancel
                    </button>
                    <span className="text-xs text-text-dim self-center ml-2">
                      Cmd+Enter to save
                    </span>
                  </div>
                </div>
              )}

              {/* ── Reject mode ───────────────────────── */}
              {mode === 'reject' && (
                <>
                  {/* Show message body in reject mode */}
                  <div className="bg-surface-alt/30 border border-border rounded-lg p-5 mb-4">
                    <div className="whitespace-pre-wrap text-sm text-text leading-relaxed opacity-60">
                      {msg.body}
                    </div>
                  </div>

                  <div className="p-4 bg-error/5 border border-error/20 rounded-lg">
                    <label className="block text-xs font-medium text-error mb-2">Rejection reason *</label>
                    <textarea
                      autoFocus
                      value={rejectNotes}
                      onChange={e => setRejectNotes(e.target.value)}
                      placeholder="Why is this message being rejected?"
                      rows={3}
                      className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-1 focus:ring-error"
                    />
                    <div className="flex gap-2 mt-3">
                      <button
                        onClick={handleReject}
                        disabled={!rejectNotes.trim() || updateMutation.isPending}
                        className="px-4 py-2 bg-error text-white text-sm font-medium rounded-lg hover:bg-error/90 disabled:opacity-50 transition-colors"
                      >
                        {updateMutation.isPending ? 'Rejecting...' : 'Confirm Reject'}
                      </button>
                      <button
                        onClick={() => { setMode('view'); setRejectNotes('') }}
                        className="px-4 py-2 bg-surface border border-border text-text text-sm rounded-lg hover:bg-surface-alt transition-colors"
                      >
                        Cancel
                      </button>
                      <span className="text-xs text-text-dim self-center ml-2">
                        Enter to confirm, Esc to cancel
                      </span>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* ── Bottom action bar ──────────────────────── */}
          {mode === 'view' && !isRegenerating && (
            <div className="border-t border-border-solid bg-surface px-8 py-4">
              <div className="max-w-2xl mx-auto flex items-center gap-3">
                {/* Back button */}
                <button
                  onClick={goBack}
                  disabled={currentIndex === 0}
                  className="px-3 py-2 text-sm text-text-muted hover:text-text bg-transparent border border-border rounded-lg hover:bg-surface-alt disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  title="Previous message (Left Arrow)"
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M10 4l-4 4 4 4" />
                  </svg>
                </button>

                {/* Primary actions */}
                <button
                  onClick={handleApprove}
                  disabled={updateMutation.isPending}
                  className="px-5 py-2 bg-success text-white text-sm font-medium rounded-lg hover:bg-success/90 disabled:opacity-50 transition-colors"
                  title="Approve (A or Right Arrow)"
                >
                  Approve
                </button>

                <button
                  onClick={() => setMode('reject')}
                  className="px-5 py-2 bg-error/10 text-error text-sm font-medium rounded-lg border border-error/20 hover:bg-error/20 transition-colors"
                  title="Reject (R)"
                >
                  Reject
                </button>

                <button
                  onClick={() => setMode('edit')}
                  className="px-5 py-2 bg-surface border border-border text-text text-sm rounded-lg hover:bg-surface-alt transition-colors"
                  title="Edit (E)"
                >
                  Edit
                </button>

                <button
                  onClick={handleRegenerate}
                  className="px-5 py-2 bg-surface border border-border text-text text-sm rounded-lg hover:bg-surface-alt transition-colors"
                  title="Regenerate (G)"
                >
                  Regenerate
                </button>

                {/* Spacer */}
                <div className="flex-1" />

                {/* Skip/Next */}
                <button
                  onClick={handleSkip}
                  className="px-3 py-2 text-sm text-text-muted hover:text-text bg-transparent border border-border rounded-lg hover:bg-surface-alt transition-colors"
                  title="Skip / Next (N)"
                >
                  Skip
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="inline-block ml-1">
                    <path d="M6 4l4 4-4 4" />
                  </svg>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Inline styles for slide animations */}
      <style>{`
        @keyframes slideLeft {
          from { opacity: 0; transform: translateX(20px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes slideRight {
          from { opacity: 0; transform: translateX(-20px); }
          to { opacity: 1; transform: translateX(0); }
        }
        .animate-slide-left {
          animation: slideLeft 0.2s ease-out;
        }
        .animate-slide-right {
          animation: slideRight 0.2s ease-out;
        }
      `}</style>
    </div>
  )
}
