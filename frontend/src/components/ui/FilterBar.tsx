import { useRef, useEffect, useState, type ReactNode } from 'react'

export interface FilterConfig {
  key: string
  label: string
  type: 'search' | 'select' | 'number'
  placeholder?: string
  options?: { value: string; label: string }[]
  min?: number
  max?: number
}

interface FilterBarProps {
  filters: FilterConfig[]
  values: Record<string, string>
  onChange: (key: string, value: string) => void
  total?: number
  action?: ReactNode
}

export function FilterBar({ filters, values, onChange, total, action }: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 mb-3">
      {filters.map((f) =>
        f.type === 'search' ? (
          <SearchInput
            key={f.key}
            placeholder={f.placeholder || `Search ${f.label}...`}
            value={values[f.key] || ''}
            onChange={(v) => onChange(f.key, v)}
          />
        ) : f.type === 'number' ? (
          <NumberInput
            key={f.key}
            placeholder={f.placeholder || f.label}
            value={values[f.key] || ''}
            min={f.min}
            max={f.max}
            onChange={(v) => onChange(f.key, v)}
          />
        ) : (
          <SelectFilter
            key={f.key}
            label={f.label}
            value={values[f.key] || ''}
            options={f.options || []}
            onChange={(v) => onChange(f.key, v)}
          />
        ),
      )}
      {total !== undefined && (
        <span className="text-sm text-text-muted ml-auto">
          {total.toLocaleString()} result{total !== 1 ? 's' : ''}
        </span>
      )}
      {action}
    </div>
  )
}

/* ---- SearchInput with 400ms debounce ---- */

function SearchInput({
  placeholder,
  value,
  onChange,
}: {
  placeholder: string
  value: string
  onChange: (v: string) => void
}) {
  const [local, setLocal] = useState(value)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  // Sync external value changes
  useEffect(() => {
    setLocal(value)
  }, [value])

  const handleChange = (v: string) => {
    setLocal(v)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => onChange(v), 400)
  }

  useEffect(() => () => clearTimeout(timer.current), [])

  return (
    <div className="relative flex-1 min-w-[180px] max-w-md">
      <svg
        width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"
        className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-dim"
      >
        <circle cx="7" cy="7" r="4.5" />
        <path d="M10.5 10.5L14 14" />
      </svg>
      <input
        type="text"
        value={local}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-8 pr-3 py-1.5 text-sm bg-surface-alt border border-border-solid rounded-md text-text placeholder:text-text-dim focus:outline-none focus:border-accent"
      />
    </div>
  )
}

/* ---- NumberInput ---- */

function NumberInput({
  placeholder,
  value,
  min,
  max,
  onChange,
}: {
  placeholder: string
  value: string
  min?: number
  max?: number
  onChange: (v: string) => void
}) {
  return (
    <input
      type="number"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      min={min}
      max={max}
      className="w-20 px-2 py-1.5 text-sm bg-surface-alt border border-border-solid rounded-md text-text placeholder:text-text-dim focus:outline-none focus:border-accent [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
    />
  )
}

/* ---- SelectFilter ---- */

function SelectFilter({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (v: string) => void
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="px-2 py-1.5 text-sm bg-surface-alt border border-border-solid rounded-md text-text focus:outline-none focus:border-accent"
    >
      <option value="">All {label}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}
