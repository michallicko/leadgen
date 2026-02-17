interface TimelineEntry {
  label: string
  timestamp: string | null
  cost?: number | null
  detail?: string | null
  status?: 'completed' | 'failed' | 'skipped' | null
  error?: string | null
}

interface EnrichmentTimelineProps {
  entries: TimelineEntry[]
}

const STATUS_COLORS: Record<string, { dot: string; text: string }> = {
  completed: { dot: 'bg-success border-success/40', text: 'text-success' },
  failed: { dot: 'bg-error border-error/40', text: 'text-error' },
  skipped: { dot: 'bg-[#8B92A0] border-[#8B92A0]/40', text: 'text-text-dim' },
}

export function EnrichmentTimeline({ entries }: EnrichmentTimelineProps) {
  // Filter out entries with no timestamp
  const valid = entries.filter((e) => e.timestamp)
  if (valid.length === 0) return null

  // Sort chronologically
  const sorted = [...valid].sort(
    (a, b) => new Date(a.timestamp!).getTime() - new Date(b.timestamp!).getTime()
  )

  return (
    <div className="space-y-0">
      {sorted.map((entry, i) => {
        const colors = entry.status ? STATUS_COLORS[entry.status] : null
        const dotClass = colors?.dot ?? 'bg-accent border-accent/40'

        return (
          <div key={i} className="flex gap-3">
            {/* Timeline gutter */}
            <div className="flex flex-col items-center">
              <div className={`w-2.5 h-2.5 rounded-full border-2 flex-shrink-0 mt-1 ${dotClass}`} />
              {i < sorted.length - 1 && (
                <div className="w-px flex-1 bg-border-solid min-h-[24px]" />
              )}
            </div>
            {/* Content */}
            <div className="pb-3 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-text">{entry.label}</span>
                {entry.status && entry.status !== 'completed' && (
                  <span className={`text-xs font-medium ${colors?.text ?? 'text-text-dim'}`}>
                    {entry.status}
                  </span>
                )}
              </div>
              <div className="text-xs text-text-muted">
                {new Date(entry.timestamp!).toLocaleString()}
                {entry.cost != null && entry.cost > 0 && (
                  <span className="ml-2 text-text-dim">${entry.cost.toFixed(4)}</span>
                )}
              </div>
              {entry.detail && (
                <div className="text-xs text-text-dim mt-0.5">{entry.detail}</div>
              )}
              {entry.error && (
                <div className="text-xs text-error mt-0.5 truncate max-w-md" title={entry.error}>
                  {entry.error}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
