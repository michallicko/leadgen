/**
 * Dialog — reusable modal dialog with focus trap, Escape to close,
 * and overlay click to close. Accepts title, children (body), and
 * actions slot for flexible content.
 *
 * Usage:
 *   <Dialog open={isOpen} onClose={handleClose} title="Edit Item">
 *     <p>Dialog body content here.</p>
 *     <Dialog.Actions>
 *       <button onClick={handleClose}>Cancel</button>
 *       <button onClick={handleSave}>Save</button>
 *     </Dialog.Actions>
 *   </Dialog>
 */

import { useEffect, useRef, useCallback, type ReactNode } from 'react'

// ---------------------------------------------------------------------------
// Actions sub-component
// ---------------------------------------------------------------------------

function DialogActions({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border-solid">
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Dialog
// ---------------------------------------------------------------------------

interface DialogProps {
  open: boolean
  onClose: () => void
  title: string
  /** Optional description below the title */
  description?: string
  /** Max width class (default: max-w-sm) */
  maxWidth?: string
  children: ReactNode
}

export function Dialog({
  open,
  onClose,
  title,
  description,
  maxWidth = 'max-w-sm',
  children,
}: DialogProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      if (e.key === 'Tab') {
        const dialog = dialogRef.current
        if (!dialog) return
        const focusable = dialog.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
        )
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    },
    [onClose],
  )

  useEffect(() => {
    if (!open) return
    document.addEventListener('keydown', handleKeyDown)
    document.body.style.overflow = 'hidden'

    // Focus first focusable element
    const dialog = dialogRef.current
    if (dialog) {
      const focusable = dialog.querySelector<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )
      focusable?.focus()
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [open, handleKeyDown])

  if (!open) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose()
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        className={`w-full ${maxWidth} bg-surface rounded-lg border border-border-solid shadow-2xl shadow-black/40 mx-4`}
      >
        <div className="px-6 py-5">
          <h2 id="dialog-title" className="text-base font-semibold font-title text-text mb-1">
            {title}
          </h2>
          {description && (
            <p className="text-sm text-text-muted">{description}</p>
          )}
        </div>
        {children}
      </div>
    </div>
  )
}

Dialog.Actions = DialogActions
