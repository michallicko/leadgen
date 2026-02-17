import { useRef, useState, useEffect, useCallback, type ReactNode } from 'react'

const ROW_HEIGHT = 41
const BUFFER = 20

export interface Column<T> {
  key: string
  label: string
  sortKey?: string
  render?: (item: T) => ReactNode
  width?: string
  minWidth?: string
  shrink?: boolean
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  sort?: { field: string; dir: 'asc' | 'desc' }
  onSort?: (field: string, dir: 'asc' | 'desc') => void
  onRowClick?: (item: T) => void
  onLoadMore?: () => void
  hasMore?: boolean
  isLoading?: boolean
  emptyText?: string
  /** Enable row selection checkboxes */
  selectable?: boolean
  /** Currently selected row IDs */
  selectedIds?: Set<string>
  /** Called when selection changes */
  onSelectionChange?: (ids: Set<string>) => void
}

export function DataTable<T extends { id?: string }>({
  columns,
  data,
  sort,
  onSort,
  onRowClick,
  onLoadMore,
  hasMore,
  isLoading,
  emptyText = 'No results match your filters.',
  selectable,
  selectedIds,
  onSelectionChange,
}: DataTableProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null)
  const sentinelRef = useRef<HTMLDivElement>(null)
  const [scrollTop, setScrollTop] = useState(0)
  const [containerHeight, setContainerHeight] = useState(0)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerHeight(entry.contentRect.height)
      }
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const rafId = useRef(0)
  const handleScroll = useCallback(() => {
    cancelAnimationFrame(rafId.current)
    rafId.current = requestAnimationFrame(() => {
      if (containerRef.current) {
        setScrollTop(containerRef.current.scrollTop)
      }
    })
  }, [])

  useEffect(() => {
    const el = sentinelRef.current
    if (!el || !onLoadMore || !hasMore) return
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !isLoading) {
          onLoadMore()
        }
      },
      { root: containerRef.current, rootMargin: '200px' },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [onLoadMore, hasMore, isLoading])

  const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - BUFFER)
  const endIndex = Math.min(data.length, Math.ceil((scrollTop + containerHeight) / ROW_HEIGHT) + BUFFER)
  const visibleData = data.slice(startIndex, endIndex)
  const offsetY = startIndex * ROW_HEIGHT

  const handleSortClick = (col: Column<T>) => {
    if (!col.sortKey || !onSort) return
    const newDir = sort?.field === col.sortKey && sort.dir === 'asc' ? 'desc' : 'asc'
    onSort(col.sortKey, newDir)
  }

  // Selection helpers
  const allVisibleSelected = selectable && data.length > 0 && data.every((item) => item.id && selectedIds?.has(item.id))

  const handleSelectAll = () => {
    if (!onSelectionChange) return
    if (allVisibleSelected) {
      onSelectionChange(new Set())
    } else {
      const ids = new Set<string>()
      for (const item of data) {
        if (item.id) ids.add(item.id)
      }
      onSelectionChange(ids)
    }
  }

  const handleSelectRow = (id: string | undefined, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!id || !onSelectionChange || !selectedIds) return
    const next = new Set(selectedIds)
    if (next.has(id)) {
      next.delete(id)
    } else {
      next.add(id)
    }
    onSelectionChange(next)
  }

  const colSpan = columns.length + (selectable ? 1 : 0)

  if (!isLoading && data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-text-dim">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="mb-3 opacity-50">
          <path d="M3 7h18M3 12h18M3 17h18" />
        </svg>
        <p className="text-sm">{emptyText}</p>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 min-h-0 overflow-auto border border-border-solid rounded-lg bg-surface"
    >
      <table className="w-full text-sm border-collapse" style={{ minWidth: 700 }}>
        <thead className="sticky top-0 z-10 bg-surface-alt">
          <tr>
            {selectable && (
              <th className="w-10 px-3 py-2.5 border-b border-border-solid">
                <input
                  type="checkbox"
                  checked={allVisibleSelected ?? false}
                  onChange={handleSelectAll}
                  className="rounded border-border-solid text-accent focus:ring-accent/30 w-3.5 h-3.5"
                />
              </th>
            )}
            {columns.map((col) => (
              <th
                key={col.key}
                style={{
                  width: col.width,
                  minWidth: col.minWidth,
                }}
                onClick={() => handleSortClick(col)}
                className={`
                  text-left text-xs font-medium text-text-muted px-3 py-2.5 border-b border-border-solid whitespace-nowrap
                  ${col.sortKey ? 'cursor-pointer hover:text-text select-none' : ''}
                `}
              >
                <span className="flex items-center gap-1">
                  {col.label}
                  {col.sortKey && sort?.field === col.sortKey && (
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" className={sort.dir === 'desc' ? 'rotate-180' : ''}>
                      <path d="M6 3l3 4H3z" />
                    </svg>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {offsetY > 0 && (
            <tr><td colSpan={colSpan} style={{ height: offsetY, padding: 0, border: 0 }} /></tr>
          )}
          {visibleData.map((item, i) => {
            const isSelected = selectable && item.id && selectedIds?.has(item.id)
            return (
              <tr
                key={item.id ?? startIndex + i}
                onClick={() => onRowClick?.(item)}
                className={`border-b border-border/30 ${onRowClick ? 'cursor-pointer hover:bg-surface-alt/50' : ''} ${isSelected ? 'bg-accent/5' : ''}`}
                style={{ height: ROW_HEIGHT }}
              >
                {selectable && (
                  <td className="px-3 py-0 w-10" onClick={(e) => handleSelectRow(item.id, e)}>
                    <input
                      type="checkbox"
                      checked={!!isSelected}
                      readOnly
                      className="rounded border-border-solid text-accent focus:ring-accent/30 w-3.5 h-3.5 cursor-pointer"
                    />
                  </td>
                )}
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`px-3 py-0 text-text ${col.shrink !== false ? 'truncate' : ''}`}
                    style={{
                      maxWidth: col.width ?? '200px',
                      minWidth: col.minWidth,
                    }}
                  >
                    {col.render
                      ? col.render(item)
                      : (item as Record<string, unknown>)[col.key] as ReactNode ?? '-'}
                  </td>
                ))}
              </tr>
            )
          })}
          {endIndex < data.length && (
            <tr><td colSpan={colSpan} style={{ height: (data.length - endIndex) * ROW_HEIGHT, padding: 0, border: 0 }} /></tr>
          )}
        </tbody>
      </table>

      <div ref={sentinelRef} className="h-1" />

      {isLoading && (
        <div className="flex items-center justify-center py-4">
          <div className="w-5 h-5 border-2 border-border border-t-accent rounded-full animate-spin" />
          <span className="ml-2 text-sm text-text-muted">Loading...</span>
        </div>
      )}
    </div>
  )
}
