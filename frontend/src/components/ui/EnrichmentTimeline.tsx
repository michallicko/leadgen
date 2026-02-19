interface TimelineEntry {
  label: string
  timestamp: string | null
  cost?: number | null
  detail?: string | null
  status?: 'completed' | 'failed' | 'skipped'
  error?: string | null
}

interface EnrichmentTimelineProps {
  entries: TimelineEntry[]
}

const dotColor: Record<string, string> = {
  completed: 'bg-green-500 border-green-500/40',
  failed: 'bg-red-500 border-red-500/40',
  skipped: 'bg-text-dim border-text-dim/40',
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
        const color = entry.status ? dotColor[entry.status] : 'bg-accent border-accent/40'
        return (
          <div key={i} className="flex gap-3">
            {/* Timeline gutter */}
            <div className="flex flex-col items-center">
              <div className={`w-2.5 h-2.5 rounded-full ${color} border-2 flex-shrink-0 mt-1`} />
              {i < sorted.length - 1 && (
                <div className="w-px flex-1 bg-border-solid min-h-[24px]" />
              )}
            </div>
            {/* Content */}
            <div className="pb-3 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-text">{entry.label}</span>
                {entry.status && entry.status !== 'completed' && (
                  <span className={`text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded ${
                    entry.status === 'failed' ? 'bg-red-500/10 text-red-400' : 'bg-text-dim/10 text-text-dim'
                  }`}>
                    {entry.status}
                  </span>
                )}
              </div>
              <div className="text-xs text-text-muted">
                {new Date(entry.timestamp!).toLocaleString()}
                {entry.cost != null && (
                  <span className="ml-2 text-text-dim">${entry.cost.toFixed(4)}</span>
                )}
              </div>
              {entry.error && (
                <div className="text-xs text-red-400 mt-0.5">{entry.error}</div>
              )}
              {entry.detail && (
                <div className="text-xs text-text-dim mt-0.5">{entry.detail}</div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
