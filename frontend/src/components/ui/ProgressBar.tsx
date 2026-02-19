interface ProgressBarProps {
  value: number
  label?: string
  detail?: string
}

export function ProgressBar({ value, label, detail }: ProgressBarProps) {
  const clampedWidth = `${Math.min(100, Math.max(0, value))}%`

  return (
    <div>
      {label && (
        <div className="text-sm text-text mb-1.5">{label}</div>
      )}
      <div className="bg-surface-alt rounded-full h-2">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{
            width: clampedWidth,
            background: 'linear-gradient(to right, var(--color-accent-cyan), var(--color-accent))',
          }}
        />
      </div>
      {detail && (
        <div className="text-xs text-text-muted text-right mt-1">{detail}</div>
      )}
    </div>
  )
}
