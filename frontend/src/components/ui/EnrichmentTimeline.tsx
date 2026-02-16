interface TimelineEntry {
  label: string
  timestamp: string | null
  cost?: number | null
  detail?: string | null
}

interface EnrichmentTimelineProps {
  entries: TimelineEntry[]
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
      {sorted.map((entry, i) => (
        <div key={i} className="flex gap-3">
          {/* Timeline gutter */}
          <div className="flex flex-col items-center">
            <div className="w-2.5 h-2.5 rounded-full bg-accent border-2 border-accent/40 flex-shrink-0 mt-1" />
            {i < sorted.length - 1 && (
              <div className="w-px flex-1 bg-border-solid min-h-[24px]" />
            )}
          </div>
          {/* Content */}
          <div className="pb-3 min-w-0">
            <div className="text-sm font-medium text-text">{entry.label}</div>
            <div className="text-xs text-text-muted">
              {new Date(entry.timestamp!).toLocaleString()}
              {entry.cost != null && (
                <span className="ml-2 text-text-dim">${entry.cost.toFixed(4)}</span>
              )}
            </div>
            {entry.detail && (
              <div className="text-xs text-text-dim mt-0.5">{entry.detail}</div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
