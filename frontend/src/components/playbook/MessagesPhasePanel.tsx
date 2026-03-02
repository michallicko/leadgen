/**
 * MessagesPhasePanel -- playbook left-panel for the "messages" phase.
 *
 * States:
 * 1. No campaign yet: "Generate Messages" button
 * 2. Generating: progress indicator with polling
 * 3. Review mode: message list with approve/reject/edit
 * 4. Empty state: no contacts selected
 */

import { useState, useCallback, useEffect } from 'react'
import { useToast } from '../ui/Toast'
import {
  useSetupCampaign,
  usePlaybookMessages,
  useGenerateMessages,
  useUpdatePlaybookMessage,
  useBatchUpdatePlaybookMessages,
  useConfirmMessages,
  type PlaybookMessage,
} from '../../api/queries/usePlaybookMessages'

// -- Icons ------------------------------------------------------------------

function SparklesIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2L9.5 9.5 2 12l7.5 2.5L12 22l2.5-7.5L22 12l-7.5-2.5z" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8.5l3.5 3.5 6.5-7" />
    </svg>
  )
}

function XIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4l8 8M12 4l-8 8" />
    </svg>
  )
}

function EditIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11.33 2a1.89 1.89 0 0 1 2.67 2.67L5.33 13.33 2 14l.67-3.33z" />
    </svg>
  )
}

function ChevronDownIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 6l4 4 4-4" />
    </svg>
  )
}

function ChevronUpIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 10l4-4 4 4" />
    </svg>
  )
}

// -- Status Badge -----------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    draft: 'bg-surface-alt text-text-muted border-border',
    approved: 'bg-success/10 text-success border-success/30',
    rejected: 'bg-error/10 text-error border-error/30',
  }
  const style = styles[status] || styles.draft
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-full border ${style}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}

// -- Message Card -----------------------------------------------------------

interface MessageCardProps {
  message: PlaybookMessage
  onApprove: (id: string) => void
  onReject: (id: string) => void
  onResetToDraft: (id: string) => void
  onEdit: (id: string, body: string, subject?: string) => void
}

function MessageCard({ message, onApprove, onReject, onResetToDraft, onEdit }: MessageCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editBody, setEditBody] = useState(message.body)
  const [editSubject, setEditSubject] = useState(message.subject || '')

  const contactName = message.contact.full_name || 'Unknown Contact'
  const companyName = message.company?.name
  const bodyPreview = message.body.length > 200
    ? message.body.slice(0, 200) + '...'
    : message.body

  const handleSaveEdit = useCallback(() => {
    onEdit(message.id, editBody, editSubject || undefined)
    setEditing(false)
  }, [message.id, editBody, editSubject, onEdit])

  const handleCancelEdit = useCallback(() => {
    setEditBody(message.body)
    setEditSubject(message.subject || '')
    setEditing(false)
  }, [message.body, message.subject])

  return (
    <div className="border border-border rounded-lg bg-surface hover:border-border-solid transition-colors">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-text truncate">
              {contactName}
            </span>
            {companyName && (
              <span className="text-xs text-text-dim truncate">
                at {companyName}
              </span>
            )}
          </div>
          {message.contact.job_title && (
            <p className="text-xs text-text-muted mt-0.5 truncate">
              {message.contact.job_title}
            </p>
          )}
        </div>
        <StatusBadge status={message.status} />
        <button
          onClick={() => setExpanded(!expanded)}
          className="p-1 text-text-muted hover:text-text transition-colors bg-transparent border-none cursor-pointer"
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          {expanded ? <ChevronUpIcon /> : <ChevronDownIcon />}
        </button>
      </div>

      {/* Subject line */}
      {message.subject && !editing && (
        <div className="px-4 pb-1">
          <span className="text-xs font-medium text-text-muted">Subject: </span>
          <span className="text-xs text-text">{message.subject}</span>
        </div>
      )}

      {/* Body (preview or full) */}
      {!editing && (
        <div className="px-4 pb-3">
          <p className="text-sm text-text leading-relaxed whitespace-pre-wrap">
            {expanded ? message.body : bodyPreview}
          </p>
          {!expanded && message.body.length > 200 && (
            <button
              onClick={() => setExpanded(true)}
              className="text-xs text-accent hover:text-accent-hover mt-1 bg-transparent border-none cursor-pointer p-0"
            >
              Show more
            </button>
          )}
        </div>
      )}

      {/* Editing mode */}
      {editing && (
        <div className="px-4 pb-3 space-y-2">
          {message.subject !== null && (
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">Subject</label>
              <input
                type="text"
                value={editSubject}
                onChange={(e) => setEditSubject(e.target.value)}
                className="w-full px-3 py-1.5 text-sm rounded-md border border-border-solid bg-surface-alt text-text focus:outline-none focus:ring-2 focus:ring-accent/40"
              />
            </div>
          )}
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">Message</label>
            <textarea
              value={editBody}
              onChange={(e) => setEditBody(e.target.value)}
              rows={6}
              className="w-full px-3 py-2 text-sm rounded-md border border-border-solid bg-surface-alt text-text focus:outline-none focus:ring-2 focus:ring-accent/40 resize-y"
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button
              onClick={handleCancelEdit}
              className="px-3 py-1.5 text-xs font-medium rounded-md border border-border-solid text-text-muted hover:bg-surface-alt transition-colors bg-transparent cursor-pointer"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveEdit}
              className="px-3 py-1.5 text-xs font-medium rounded-md bg-accent text-white hover:bg-accent-hover transition-colors cursor-pointer"
            >
              Save
            </button>
          </div>
        </div>
      )}

      {/* Actions */}
      {!editing && (
        <div className="flex items-center gap-2 px-4 py-2 border-t border-border bg-surface-alt/50 rounded-b-lg">
          {message.status !== 'approved' && (
            <button
              onClick={() => onApprove(message.id)}
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md text-success hover:bg-success/10 transition-colors bg-transparent border border-success/30 cursor-pointer"
            >
              <CheckIcon />
              Approve
            </button>
          )}
          {message.status !== 'rejected' && (
            <button
              onClick={() => onReject(message.id)}
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md text-error hover:bg-error/10 transition-colors bg-transparent border border-error/30 cursor-pointer"
            >
              <XIcon />
              Reject
            </button>
          )}
          <button
            onClick={() => {
              setEditBody(message.body)
              setEditSubject(message.subject || '')
              setEditing(true)
              setExpanded(true)
            }}
            className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md text-text-muted hover:bg-surface-alt transition-colors bg-transparent border border-border cursor-pointer"
          >
            <EditIcon />
            Edit
          </button>
          {message.status === 'approved' && (
            <button
              onClick={() => onResetToDraft(message.id)}
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md text-text-muted hover:bg-surface-alt transition-colors bg-transparent border border-border cursor-pointer ml-auto"
            >
              Unapprove
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// -- Filter Tabs ------------------------------------------------------------

interface FilterTabsProps {
  current: string
  counts: Record<string, number>
  onChange: (status: string) => void
}

function FilterTabs({ current, counts, onChange }: FilterTabsProps) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0)
  const tabs = [
    { key: '', label: 'All', count: total },
    { key: 'draft', label: 'Draft', count: counts.draft || 0 },
    { key: 'approved', label: 'Approved', count: counts.approved || 0 },
    { key: 'rejected', label: 'Rejected', count: counts.rejected || 0 },
  ]

  return (
    <div className="flex gap-1 p-1 bg-surface-alt rounded-lg">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer border-none ${
            current === tab.key
              ? 'bg-surface text-text shadow-sm'
              : 'bg-transparent text-text-muted hover:text-text'
          }`}
        >
          {tab.label}
          {tab.count > 0 && (
            <span className="ml-1 text-text-dim">({tab.count})</span>
          )}
        </button>
      ))}
    </div>
  )
}

// -- Main Component ---------------------------------------------------------

interface MessagesPhaseProps {
  playbookId: string | undefined
  onPhaseAdvance?: (phase: string) => void
}

export function MessagesPhasePanel({ playbookId, onPhaseAdvance }: MessagesPhaseProps) {
  const { toast } = useToast()
  const [statusFilter, setStatusFilter] = useState('')
  const [setupDone, setSetupDone] = useState(false)

  const setupMutation = useSetupCampaign(playbookId)
  const messagesQuery = usePlaybookMessages(playbookId, {
    status: statusFilter || undefined,
    enabled: setupDone,
  })
  const generateMutation = useGenerateMessages(playbookId)
  const updateMutation = useUpdatePlaybookMessage(playbookId)
  const batchMutation = useBatchUpdatePlaybookMessages(playbookId)
  const confirmMutation = useConfirmMessages(playbookId)

  // Auto-setup campaign on mount
  useEffect(() => {
    if (!playbookId || setupDone || setupMutation.isPending) return
    setupMutation.mutate(undefined, {
      onSuccess: () => setSetupDone(true),
      onError: () => setSetupDone(true), // Still allow viewing even if setup fails
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playbookId])

  const contactCount = setupMutation.data?.total_contacts ?? 0

  const data = messagesQuery.data
  const messages = data?.messages || []
  const campaignStatus = data?.campaign_status
  const statusCounts = data?.status_counts || {}
  const approvedCount = statusCounts.approved || 0
  const totalMessages = data?.total || 0

  // -- Callbacks (must be before any early returns per React hooks rules) ----

  const handleApprove = useCallback(
    (messageId: string) => {
      updateMutation.mutate(
        { messageId, data: { status: 'approved' } },
        {
          onError: () => toast('Failed to approve message', 'error'),
        },
      )
    },
    [updateMutation, toast],
  )

  const handleReject = useCallback(
    (messageId: string) => {
      updateMutation.mutate(
        { messageId, data: { status: 'rejected' } },
        {
          onError: () => toast('Failed to reject message', 'error'),
        },
      )
    },
    [updateMutation, toast],
  )

  const handleEdit = useCallback(
    (messageId: string, body: string, subject?: string) => {
      updateMutation.mutate(
        { messageId, data: { body, subject } },
        {
          onSuccess: () => toast('Message updated', 'success'),
          onError: () => toast('Failed to update message', 'error'),
        },
      )
    },
    [updateMutation, toast],
  )

  const handleResetToDraft = useCallback(
    (messageId: string) => {
      updateMutation.mutate(
        { messageId, data: { status: 'draft' } },
        {
          onError: () => toast('Failed to reset message', 'error'),
        },
      )
    },
    [updateMutation, toast],
  )

  const handleBatchApprove = useCallback(() => {
    batchMutation.mutate(
      { action: 'approve_all' },
      {
        onSuccess: (res) => toast(`${res.updated} messages approved`, 'success'),
        onError: () => toast('Batch approve failed', 'error'),
      },
    )
  }, [batchMutation, toast])

  const handleBatchReject = useCallback(() => {
    batchMutation.mutate(
      { action: 'reject_all' },
      {
        onSuccess: (res) => toast(`${res.updated} messages rejected`, 'info'),
        onError: () => toast('Batch reject failed', 'error'),
      },
    )
  }, [batchMutation, toast])

  const handleConfirm = useCallback(() => {
    confirmMutation.mutate(undefined, {
      onSuccess: () => {
        toast('Messages confirmed. Moving to Campaign phase...', 'success')
        onPhaseAdvance?.('campaign')
      },
      onError: (err) =>
        toast(
          err instanceof Error ? err.message : 'Confirmation failed',
          'error',
        ),
    })
  }, [confirmMutation, toast, onPhaseAdvance])

  // -- Setup in progress ---------------------------------------------------

  if (!setupDone) {
    return (
      <div className="flex-1 min-h-0 flex items-center justify-center">
        <div className="text-center max-w-md px-6">
          <div className="w-8 h-8 border-2 border-border border-t-accent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm text-text-muted">Setting up campaign...</p>
        </div>
      </div>
    )
  }

  // -- Setup failed with no contacts -------------------------------------------

  if (setupMutation.isError) {
    const errMsg = setupMutation.error instanceof Error
      ? setupMutation.error.message
      : 'Campaign setup failed'
    const isNoContacts = errMsg.toLowerCase().includes('no contacts')

    return (
      <div className="flex-1 min-h-0 flex items-center justify-center">
        <div className="text-center max-w-md px-6">
          <div className="w-14 h-14 rounded-2xl bg-warning/10 flex items-center justify-center mx-auto mb-5">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-warning">
              <path d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold font-title text-text mb-2">
            {isNoContacts ? 'No contacts selected' : 'Setup failed'}
          </h2>
          <p className="text-sm text-text-muted leading-relaxed">
            {isNoContacts
              ? 'Go back to the Contacts phase to select target contacts for your outreach campaign.'
              : errMsg}
          </p>
        </div>
      </div>
    )
  }

  // -- No campaign yet / no messages: show generate button --------------------------------

  if ((!data?.campaign_id || totalMessages === 0) && !generateMutation.isPending && campaignStatus !== 'generating') {
    return (
      <div className="flex-1 min-h-0 flex items-center justify-center">
        <div className="text-center max-w-md px-6">
          <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-5">
            <SparklesIcon />
          </div>
          <h2 className="text-lg font-semibold font-title text-text mb-2">
            Ready to generate messages
          </h2>
          <p className="text-sm text-text-muted leading-relaxed mb-6">
            {contactCount} contact{contactCount !== 1 ? 's' : ''} selected.
            AI will craft personalized outreach messages using your strategy and enrichment data.
          </p>
          <button
            onClick={() => {
              generateMutation.mutate(undefined, {
                onSuccess: () => toast('Message generation started', 'info'),
                onError: (err) =>
                  toast(
                    err instanceof Error ? err.message : 'Failed to start generation',
                    'error',
                  ),
              })
            }}
            disabled={generateMutation.isPending}
            className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <SparklesIcon />
            Generate Messages
          </button>
          {generateMutation.isError && (
            <p className="text-xs text-error mt-3">
              {generateMutation.error instanceof Error
                ? generateMutation.error.message
                : 'Generation failed'}
            </p>
          )}
        </div>
      </div>
    )
  }

  // -- Generating state -----------------------------------------------------

  if (campaignStatus === 'generating' || generateMutation.isPending) {
    const generated = statusCounts.draft || 0
    const approved = statusCounts.approved || 0
    const total = generated + approved + (statusCounts.rejected || 0)

    return (
      <div className="flex-1 min-h-0 flex items-center justify-center">
        <div className="text-center max-w-md px-6">
          <div className="w-14 h-14 rounded-2xl bg-accent-cyan/10 flex items-center justify-center mx-auto mb-5">
            <div className="w-6 h-6 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
          </div>
          <h2 className="text-lg font-semibold font-title text-text mb-2">
            Generating messages...
          </h2>
          <p className="text-sm text-text-muted leading-relaxed mb-4">
            {total > 0
              ? `${total} message${total !== 1 ? 's' : ''} generated so far`
              : 'Starting generation...'}
          </p>
          <div className="w-full bg-surface-alt rounded-full h-2 overflow-hidden">
            <div
              className="h-full bg-accent-cyan rounded-full transition-all duration-500"
              style={{ width: `${contactCount > 0 ? Math.min((total / contactCount) * 100, 100) : 0}%` }}
            />
          </div>
          <p className="text-xs text-text-dim mt-2">
            This may take a minute. Messages will appear as they are generated.
          </p>
        </div>
      </div>
    )
  }

  // -- Loading state --------------------------------------------------------

  if (messagesQuery.isLoading) {
    return (
      <div className="flex-1 min-h-0 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-border border-t-accent rounded-full animate-spin" />
      </div>
    )
  }

  // -- Review mode ----------------------------------------------------------

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3 pb-3 flex-shrink-0">
        <FilterTabs
          current={statusFilter}
          counts={statusCounts}
          onChange={setStatusFilter}
        />
        <div className="flex items-center gap-2">
          <button
            onClick={handleBatchApprove}
            disabled={batchMutation.isPending}
            className="px-3 py-1.5 text-xs font-medium rounded-md text-success border border-success/30 hover:bg-success/10 transition-colors bg-transparent cursor-pointer disabled:opacity-40"
          >
            Approve All
          </button>
          <button
            onClick={handleBatchReject}
            disabled={batchMutation.isPending}
            className="px-3 py-1.5 text-xs font-medium rounded-md text-error border border-error/30 hover:bg-error/10 transition-colors bg-transparent cursor-pointer disabled:opacity-40"
          >
            Reject All
          </button>
        </div>
      </div>

      {/* Message list */}
      <div className="flex-1 min-h-0 overflow-y-auto space-y-3 pb-20">
        {messages.length === 0 && (
          <div className="text-center py-10 text-sm text-text-muted">
            {statusFilter
              ? `No ${statusFilter} messages`
              : 'No messages generated yet'}
          </div>
        )}
        {messages.map((msg) => (
          <MessageCard
            key={msg.id}
            message={msg}
            onApprove={handleApprove}
            onReject={handleReject}
            onResetToDraft={handleResetToDraft}
            onEdit={handleEdit}
          />
        ))}
      </div>

      {/* Footer: confirm bar */}
      {totalMessages > 0 && (
        <div className="sticky bottom-0 bg-surface border-t border-border px-4 py-3 flex items-center justify-between flex-shrink-0">
          <p className="text-sm text-text">
            <span className="font-medium text-success">{approvedCount}</span>
            {' '}of{' '}
            <span className="font-medium">{totalMessages}</span>
            {' '}message{totalMessages !== 1 ? 's' : ''} approved
          </p>
          <button
            onClick={handleConfirm}
            disabled={approvedCount === 0 || confirmMutation.isPending}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {confirmMutation.isPending
              ? 'Confirming...'
              : `Confirm & Continue (${approvedCount})`}
          </button>
        </div>
      )}
    </div>
  )
}
