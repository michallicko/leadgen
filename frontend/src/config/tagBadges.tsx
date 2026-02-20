/* eslint-disable react-refresh/only-export-components */

/**
 * Compact tag badge renderer shared by company and contact column configs.
 * Shows at most 2 tags inline as pill badges, with a +N overflow indicator.
 */
export function renderTagBadges(names: string[] | undefined) {
  if (!names || names.length === 0) {
    return <span className="text-text-dim">-</span>
  }

  const visible = names.slice(0, 2)
  const overflow = names.length - visible.length

  return (
    <span className="flex items-center gap-1 overflow-hidden">
      {visible.map((tag) => (
        <span
          key={tag}
          title={tag}
          className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface-alt text-text-muted truncate max-w-[80px]"
        >
          {tag}
        </span>
      ))}
      {overflow > 0 && (
        <span
          title={names.slice(2).join(', ')}
          className="text-[10px] text-text-dim flex-shrink-0"
        >
          +{overflow}
        </span>
      )}
    </span>
  )
}
