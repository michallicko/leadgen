import { useState, useRef, useEffect, useCallback } from 'react'
import { apiFetch } from '../../api/client'
import './MultiSelectFilter.css'

interface JobTitleFilterProps {
  selected: string[]
  exclude: boolean
  onSelectionChange: (values: string[]) => void
  onExcludeToggle: () => void
  className?: string
}

interface TitleSuggestion {
  title: string
  count: number
}

export function JobTitleFilter({
  selected,
  exclude,
  onSelectionChange,
  onExcludeToggle,
  className = '',
}: JobTitleFilterProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState<TitleSuggestion[]>([])
  const [loading, setLoading] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
        setQuery('')
        setSuggestions([])
      }
    }
    if (open) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const fetchSuggestions = useCallback(async (q: string) => {
    if (q.length < 2) {
      setSuggestions([])
      return
    }
    setLoading(true)
    try {
      const data = await apiFetch<{ titles: TitleSuggestion[] }>(
        `/contacts/job-titles`,
        { params: { q, limit: '20' } },
      )
      const filtered = data.titles.filter(
        t => !selected.includes(t.title)
      )
      setSuggestions(filtered)
    } catch {
      setSuggestions([])
    } finally {
      setLoading(false)
    }
  }, [selected])

  const handleInput = (value: string) => {
    setQuery(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => fetchSuggestions(value), 300)
  }

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  const addTitle = (title: string) => {
    onSelectionChange([...selected, title])
    setQuery('')
    setSuggestions([])
    inputRef.current?.focus()
  }

  const removeTitle = (title: string) => {
    onSelectionChange(selected.filter(t => t !== title))
  }

  const hasSelection = selected.length > 0

  return (
    <div ref={ref} className={`msf ${className}`}>
      <button
        className={`msf-trigger ${hasSelection ? (exclude ? 'msf-has-exclude' : 'msf-has-selection') : ''}`}
        onClick={() => { setOpen(!open); setTimeout(() => inputRef.current?.focus(), 50) }}
        type="button"
      >
        <span className="msf-label">Job Title</span>
        {hasSelection ? (
          <span className="msf-chips">
            {exclude && <span className="msf-not-badge">NOT</span>}
            {selected.slice(0, 2).map(t => (
              <span key={t} className={`msf-chip ${exclude ? 'msf-chip-exclude' : ''}`}>
                {t}
                <span className="msf-chip-remove" onClick={(e) => { e.stopPropagation(); removeTitle(t) }}>&times;</span>
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

      {open && (
        <div className="msf-dropdown">
          <div className="msf-search">
            <input
              ref={inputRef}
              type="text"
              placeholder="Search job titles..."
              value={query}
              onChange={e => handleInput(e.target.value)}
            />
          </div>
          <div className="msf-options">
            {loading && <div className="msf-empty">Searching...</div>}
            {!loading && query.length >= 2 && suggestions.length === 0 && (
              <div className="msf-empty">No titles match</div>
            )}
            {!loading && query.length < 2 && suggestions.length === 0 && (
              <div className="msf-empty">Type 2+ chars to search</div>
            )}
            {suggestions.map(s => (
              <label
                key={s.title}
                className="msf-option"
                onClick={() => addTitle(s.title)}
              >
                <span className="msf-option-label">{s.title}</span>
                <span className="msf-option-count">({s.count})</span>
              </label>
            ))}
          </div>
          {hasSelection && (
            <button
              className="msf-clear"
              onClick={() => { onSelectionChange([]); setQuery(''); setSuggestions([]) }}
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
