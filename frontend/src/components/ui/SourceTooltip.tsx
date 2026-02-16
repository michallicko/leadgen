import { useState, useRef, useEffect } from 'react'

export interface SourceInfo {
  label: string
  timestamp?: string | null
  cost?: number | null
}

interface SourceTooltipProps {
  source: SourceInfo
}

export function SourceTooltip({ source }: SourceTooltipProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  return (
    <div className="relative inline-block ml-1" ref={ref}>
      <button
        onClick={(e) => { e.stopPropagation(); setOpen(!open) }}
        className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-text-dim/20 text-text-dim hover:bg-accent/20 hover:text-accent-cyan transition-colors text-[9px] font-bold leading-none"
        aria-label="Source info"
      >
        i
      </button>
      {open && (
        <div className="absolute left-0 top-5 z-50 w-48 p-2 rounded-md bg-surface-alt border border-border-solid shadow-lg shadow-black/30 text-xs">
          <div className="font-medium text-text mb-1">{source.label}</div>
          {source.timestamp && (
            <div className="text-text-muted">
              {new Date(source.timestamp).toLocaleString()}
            </div>
          )}
          {source.cost != null && (
            <div className="text-text-dim">Cost: ${source.cost.toFixed(4)}</div>
          )}
        </div>
      )}
    </div>
  )
}
