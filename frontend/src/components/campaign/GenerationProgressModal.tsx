import { useEffect, useRef, useState, useCallback } from 'react'
import { useGenerationStatus, useCancelGeneration } from '../../api/queries/useCampaignGeneration'
import { ProgressBar } from '../ui/ProgressBar'
import { useToast } from '../ui/Toast'

interface Props {
  campaignId: string
  isOpen: boolean
  onClose: () => void
}

/**
 * Modal that polls generation status every 2s, showing real-time progress.
 * Supports minimize-to-toast, cancel with confirmation, and auto-close on completion.
 */
export function GenerationProgressModal({ campaignId, isOpen, onClose }: Props) {
  const { toast } = useToast()
  const cancelGeneration = useCancelGeneration()
  const overlayRef = useRef<HTMLDivElement>(null)

  const [showCancelConfirm, setShowCancelConfirm] = useState(false)
  const [minimized, setMinimized] = useState(false)
  const prevStatusRef = useRef<string | null>(null)

  // Poll while the modal is logically open (even if minimized)
  const { data: status } = useGenerationStatus(campaignId, isOpen)

  // Auto-close when generation completes (status transitions away from "Generating")
  useEffect(() => {
    if (!status) return
    const prev = prevStatusRef.current
    prevStatusRef.current = status.status

    if (prev === 'Generating' && status.status !== 'Generating') {
      if (minimized) {
        toast(`Generation complete: ${status.generated_count} messages`, 'success')
      }
      onClose()
    }
  }, [status, minimized, toast, onClose])

  // Escape to close
  useEffect(() => {
    if (!isOpen || minimized) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showCancelConfirm) {
          setShowCancelConfirm(false)
        } else {
          handleMinimize()
        }
      }
    }
    document.addEventListener('keydown', handler)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handler)
      document.body.style.overflow = ''
    }
  }, [isOpen, minimized, showCancelConfirm]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleMinimize = useCallback(() => {
    setMinimized(true)
    toast('Generation running in background...', 'info')
    document.body.style.overflow = ''
  }, [toast])

  const handleCancel = useCallback(async () => {
    try {
      await cancelGeneration.mutateAsync(campaignId)
      toast('Generation cancelled', 'info')
      setShowCancelConfirm(false)
      onClose()
    } catch {
      toast('Failed to cancel generation', 'error')
    }
  }, [campaignId, cancelGeneration, toast, onClose])

  // If minimized, render nothing visible (polling continues)
  if (!isOpen || minimized) return null

  const progressPct = status?.progress_pct ?? 0
  const totalContacts = status?.total_contacts ?? 0
  const generatedCount = status?.generated_count ?? 0
  const cost = status?.generation_cost ?? 0
  const channels = status?.channels
  const failedContacts = status?.failed_contacts ?? []
  const contactStatuses = status?.contact_statuses ?? {}
  const generating = contactStatuses.generating ?? 0

  // Estimate remaining time: assume ~3s per contact
  const remaining = totalContacts - generatedCount
  const etaSeconds = remaining * 3
  const etaDisplay = etaSeconds > 120
    ? `~${Math.ceil(etaSeconds / 60)} min remaining`
    : etaSeconds > 0
      ? `~${etaSeconds}s remaining`
      : 'Finishing up...'

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === overlayRef.current) handleMinimize()
      }}
    >
      <div className="relative w-full max-w-xl bg-surface rounded-lg border border-border-solid shadow-2xl shadow-black/40 mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-solid">
          <div className="flex items-center gap-3">
            {/* Animated spinner */}
            <div className="w-5 h-5 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
            <h2 className="text-lg font-semibold font-title text-text">Generating Messages</h2>
          </div>
          <button
            onClick={handleMinimize}
            className="ml-4 flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-md text-text-muted hover:text-text hover:bg-surface-alt transition-colors cursor-pointer bg-transparent border-none"
            aria-label="Minimize"
            title="Minimize to background"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 12h10" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-5">
          {/* Main progress */}
          <div>
            <div className="flex items-baseline justify-between mb-2">
              <span className="text-sm text-text">
                {generating > 0
                  ? `Processing contact ${generatedCount + 1} of ${totalContacts}...`
                  : `${generatedCount} of ${totalContacts} contacts processed`}
              </span>
              <span className="text-xs text-text-muted">{etaDisplay}</span>
            </div>
            <ProgressBar value={progressPct} />
            <div className="text-xs text-text-dim text-right mt-1">{progressPct}%</div>
          </div>

          {/* Channel breakdown */}
          {channels && Object.keys(channels).length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wider">
                By Channel
              </h3>
              {Object.entries(channels).map(([channel, stats]) => (
                <div key={channel} className="flex items-center gap-3">
                  <span className="text-xs text-text-muted w-28 truncate capitalize">
                    {channel.replace(/_/g, ' ')}
                  </span>
                  <div className="flex-1">
                    <ProgressBar
                      value={stats.target > 0 ? (stats.generated / stats.target) * 100 : 0}
                    />
                  </div>
                  <span className="text-xs text-text-dim w-14 text-right">
                    {stats.generated}/{stats.target}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Cost tracker */}
          <div className="flex items-center justify-between px-4 py-3 bg-surface-alt rounded-lg border border-border">
            <span className="text-sm text-text-muted">Est. cost</span>
            <span className="text-sm font-medium text-accent-cyan">
              ${cost.toFixed(2)}
            </span>
          </div>

          {/* Failed contacts (if any) */}
          {failedContacts.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-medium text-error uppercase tracking-wider">
                Failed ({failedContacts.length})
              </h3>
              <div className="max-h-24 overflow-y-auto space-y-1">
                {failedContacts.map((fc) => (
                  <div key={fc.contact_id} className="flex items-center gap-2 text-xs">
                    <span className="text-error">x</span>
                    <span className="text-text-muted truncate">{fc.name}</span>
                    <span className="text-text-dim truncate flex-1">{fc.error}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-border-solid">
          <button
            onClick={handleMinimize}
            className="px-3 py-1.5 text-xs font-medium rounded border border-border text-text-muted hover:text-text hover:border-border-solid cursor-pointer bg-transparent transition-colors"
          >
            Minimize
          </button>

          {!showCancelConfirm ? (
            <button
              onClick={() => setShowCancelConfirm(true)}
              className="px-3 py-1.5 text-xs font-medium rounded border border-error/30 text-error hover:bg-error/10 cursor-pointer bg-transparent transition-colors"
            >
              Cancel Generation
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-muted">Are you sure?</span>
              <button
                onClick={handleCancel}
                disabled={cancelGeneration.isPending}
                className="px-3 py-1.5 text-xs font-medium rounded bg-error text-white border-none cursor-pointer hover:bg-error/90 transition-colors disabled:opacity-50"
              >
                {cancelGeneration.isPending ? 'Cancelling...' : 'Yes, Cancel'}
              </button>
              <button
                onClick={() => setShowCancelConfirm(false)}
                className="px-3 py-1.5 text-xs font-medium rounded border border-border text-text-muted hover:text-text cursor-pointer bg-transparent transition-colors"
              >
                No
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
