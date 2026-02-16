import { useEffect, useRef, type ReactNode } from 'react'

interface DetailModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  subtitle?: string
  isLoading?: boolean
  /** Show a back arrow when true (for stack navigation). */
  canGoBack?: boolean
  /** Called when back arrow is clicked. */
  onBack?: () => void
  /** Breadcrumb text shown as a link above the title. */
  breadcrumb?: string
  children: ReactNode
}

export function DetailModal({ isOpen, onClose, title, subtitle, isLoading, canGoBack, onBack, breadcrumb, children }: DetailModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (canGoBack && onBack) {
          onBack()
        } else {
          onClose()
        }
      }
    }
    document.addEventListener('keydown', handler)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handler)
      document.body.style.overflow = ''
    }
  }, [isOpen, onClose, canGoBack, onBack])

  if (!isOpen) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-40 flex items-start justify-center bg-black/60 backdrop-blur-sm overflow-y-auto py-8"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose()
      }}
    >
      <div className="relative w-full max-w-3xl bg-surface rounded-lg border border-border-solid shadow-2xl shadow-black/40 mx-4 my-auto">
        {/* Sticky header */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 bg-surface rounded-t-lg border-b border-border-solid">
          <div className="min-w-0">
            {canGoBack && breadcrumb && (
              <button
                onClick={onBack}
                className="flex items-center gap-1 text-xs text-accent-cyan hover:underline mb-1"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M7.5 2.5L4 6l3.5 3.5" />
                </svg>
                {breadcrumb}
              </button>
            )}
            <h2 className="text-lg font-semibold font-title text-text truncate">{title}</h2>
            {subtitle && <p className="text-sm text-text-muted truncate">{subtitle}</p>}
          </div>
          <button
            onClick={onClose}
            className="ml-4 flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-md text-text-muted hover:text-text hover:bg-surface-alt transition-colors"
            aria-label="Close"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 4l8 8M12 4l-8 8" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-8 h-8 border-2 border-border border-t-accent rounded-full animate-spin" />
            </div>
          ) : (
            children
          )}
        </div>
      </div>
    </div>
  )
}
