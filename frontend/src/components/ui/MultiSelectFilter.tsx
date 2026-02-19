import { useState, useRef, useEffect, useMemo } from 'react'
import './MultiSelectFilter.css'

interface Option {
  value: string
  label: string
  count?: number
}

interface MultiSelectFilterProps {
  label: string
  options: Option[]
  selected: string[]
  exclude: boolean
  onSelectionChange: (values: string[]) => void
  onExcludeToggle: () => void
  searchable?: boolean
  className?: string
}

export function MultiSelectFilter({
  label,
  options,
  selected,
  exclude,
  onSelectionChange,
  onExcludeToggle,
  searchable = true,
  className = '',
}: MultiSelectFilterProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  // Close on click outside
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
        setSearch('')
      }
    }
    if (open) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  // Focus search on open
  useEffect(() => {
    if (open && searchRef.current) searchRef.current.focus()
  }, [open])

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    const sorted = [...options].sort((a, b) => (b.count ?? 0) - (a.count ?? 0))
    if (!q) return sorted
    return sorted.filter(o => o.label.toLowerCase().includes(q))
  }, [options, search])

  const toggleValue = (value: string) => {
    if (selected.includes(value)) {
      onSelectionChange(selected.filter(v => v !== value))
    } else {
      onSelectionChange([...selected, value])
    }
  }

  const getLabel = (value: string) => options.find(o => o.value === value)?.label ?? value

  const hasSelection = selected.length > 0

  return (
    <div ref={ref} className={`msf ${className}`}>
      {/* Trigger */}
      <button
        className={`msf-trigger ${hasSelection ? (exclude ? 'msf-has-exclude' : 'msf-has-selection') : ''}`}
        onClick={() => setOpen(!open)}
        type="button"
      >
        <span className="msf-label">{label}</span>
        {hasSelection ? (
          <span className="msf-chips">
            {exclude && <span className="msf-not-badge">NOT</span>}
            {selected.slice(0, 2).map(v => (
              <span key={v} className={`msf-chip ${exclude ? 'msf-chip-exclude' : ''}`}>
                {getLabel(v)}
                <span
                  className="msf-chip-remove"
                  onClick={(e) => { e.stopPropagation(); toggleValue(v) }}
                >
                  &times;
                </span>
              </span>
            ))}
            {selected.length > 2 && (
              <span className="msf-more">+{selected.length - 2}</span>
            )}
          </span>
        ) : (
          <span className="msf-placeholder">All</span>
        )}
        {hasSelection && (
          <button
            className="msf-exclude-toggle"
            onClick={(e) => { e.stopPropagation(); onExcludeToggle() }}
            title={exclude ? 'Switch to Include' : 'Switch to Exclude'}
            type="button"
          >
            {exclude ? '\u2296' : '\u2295'}
          </button>
        )}
        <span className="msf-arrow">{open ? '\u25B4' : '\u25BE'}</span>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="msf-dropdown">
          {searchable && (
            <div className="msf-search">
              <input
                ref={searchRef}
                type="text"
                placeholder={`Filter ${label.toLowerCase()}...`}
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
          )}
          <div className="msf-options">
            {filtered.map(opt => {
              const isSelected = selected.includes(opt.value)
              const isZero = (opt.count ?? 0) === 0 && opt.count !== undefined
              return (
                <label
                  key={opt.value}
                  className={`msf-option ${isSelected ? 'msf-option-selected' : ''} ${isZero ? 'msf-option-zero' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleValue(opt.value)}
                  />
                  <span className="msf-option-label">{opt.label}</span>
                  {opt.count !== undefined && (
                    <span className="msf-option-count">({opt.count})</span>
                  )}
                </label>
              )
            })}
            {filtered.length === 0 && (
              <div className="msf-empty">No options match</div>
            )}
          </div>
          {hasSelection && (
            <button
              className="msf-clear"
              onClick={() => { onSelectionChange([]); setSearch('') }}
              type="button"
            >
              Clear selection
            </button>
          )}
        </div>
      )}
    </div>
  )
}
