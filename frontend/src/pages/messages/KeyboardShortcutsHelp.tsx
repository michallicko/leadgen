import { useEffect } from 'react'

interface KeyboardShortcutsHelpProps {
  onClose: () => void
}

const SHORTCUTS = [
  { key: 'j', description: 'Move to next contact group' },
  { key: 'k', description: 'Move to previous contact group' },
  { key: 'a', description: 'Approve focused group\'s draft A messages' },
  { key: 'r', description: 'Reject focused group\'s draft messages' },
  { key: 'Shift+A', description: 'Approve all visible draft A messages' },
  { key: '?', description: 'Toggle this help overlay' },
  { key: 'Esc', description: 'Close overlay / clear focus' },
]

export function KeyboardShortcutsHelp({ onClose }: KeyboardShortcutsHelpProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' || e.key === '?') {
        e.preventDefault()
        onClose()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-bg border border-border rounded-xl shadow-xl max-w-sm w-full mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-text">Keyboard Shortcuts</h3>
          <button onClick={onClose} className="text-text-dim hover:text-text text-lg">
            &times;
          </button>
        </div>

        <div className="space-y-2">
          {SHORTCUTS.map((s) => (
            <div key={s.key} className="flex items-center justify-between py-1">
              <span className="text-sm text-text-muted">{s.description}</span>
              <kbd className="px-2 py-1 bg-surface-alt border border-border-solid rounded text-xs font-mono text-text min-w-[2rem] text-center">
                {s.key}
              </kbd>
            </div>
          ))}
        </div>

        <div className="mt-4 pt-3 border-t border-border text-xs text-text-dim">
          Shortcuts are disabled when a text field is focused.
        </div>
      </div>
    </div>
  )
}
