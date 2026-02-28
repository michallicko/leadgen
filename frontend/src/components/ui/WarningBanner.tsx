import { type ReactNode } from 'react'

interface WarningBannerProps {
  message: ReactNode
  variant?: 'warning' | 'info'
  icon?: ReactNode
  onDismiss?: () => void
}

const VARIANT_STYLES = {
  warning: 'bg-warning/10 border-warning/30 text-warning',
  info: 'bg-accent-cyan/10 border-accent-cyan/30 text-accent-cyan',
}

const DEFAULT_ICONS: Record<string, ReactNode> = {
  warning: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M8 1.5L1.5 13h13L8 1.5z" />
      <path d="M8 6v3M8 11v.01" />
    </svg>
  ),
  info: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="8" cy="8" r="6.5" />
      <path d="M8 7v4M8 5v.01" />
    </svg>
  ),
}

export function WarningBanner({ message, variant = 'warning', icon, onDismiss }: WarningBannerProps) {
  return (
    <div className={`flex items-start gap-2.5 px-4 py-3 rounded-lg border text-sm ${VARIANT_STYLES[variant]}`}>
      <span className="flex-shrink-0 mt-0.5">
        {icon ?? DEFAULT_ICONS[variant]}
      </span>
      <div className="flex-1 min-w-0">{message}</div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="flex-shrink-0 p-0.5 rounded hover:bg-black/10 transition-colors bg-transparent border-none cursor-pointer"
          aria-label="Dismiss"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M3.5 3.5l7 7M10.5 3.5l-7 7" />
          </svg>
        </button>
      )}
    </div>
  )
}
