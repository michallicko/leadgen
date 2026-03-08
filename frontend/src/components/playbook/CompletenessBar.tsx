/**
 * CompletenessBar -- horizontal progress bar showing strategy section completion.
 *
 * Renders:
 * - Progress bar with "N/M sections complete" label
 * - Row of section dots (filled=green, empty=gray)
 * - Tooltip on hover showing section name
 *
 * Layer 1 of the two-layer quality scoring system (BL-1016).
 * Always visible, no LLM call required.
 */

interface CompletenessBarProps {
  filled: number
  total: number
  sections: Record<string, boolean>
}

export function CompletenessBar({ filled, total, sections }: CompletenessBarProps) {
  const ratio = total > 0 ? filled / total : 0
  const pct = Math.round(ratio * 100)

  return (
    <div className="flex items-center gap-3 px-3 py-1.5">
      {/* Label */}
      <span className="text-xs text-text-muted whitespace-nowrap">
        {filled}/{total} sections
      </span>

      {/* Progress bar */}
      <div className="flex-1 h-1.5 bg-surface-alt rounded-full overflow-hidden min-w-[60px] max-w-[160px]">
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{
            width: `${pct}%`,
            backgroundColor: ratio >= 0.8 ? 'var(--color-success, #22c55e)' :
                             ratio >= 0.4 ? 'var(--color-warning, #f59e0b)' :
                                            'var(--color-text-muted, #9ca3af)',
          }}
        />
      </div>

      {/* Section dots */}
      <div className="flex items-center gap-1">
        {Object.entries(sections).map(([name, isFilled]) => (
          <div
            key={name}
            title={`${name}: ${isFilled ? 'Complete' : 'Empty'}`}
            className={`w-2 h-2 rounded-full transition-colors cursor-default ${
              isFilled
                ? 'bg-[var(--color-success,#22c55e)]'
                : 'bg-[var(--color-border-solid,#d1d5db)]'
            }`}
          />
        ))}
      </div>
    </div>
  )
}
