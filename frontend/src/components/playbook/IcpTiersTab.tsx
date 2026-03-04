/**
 * IcpTiersTab -- structured ICP tier definitions with inline editing.
 *
 * Each tier renders as an editable card with name, description, priority,
 * and structured criteria (industries, company size range, revenue range,
 * geographies, tech signals, qualifying signals).
 *
 * Data is stored in extracted_data.tiers via the /api/playbook/strategy/tiers
 * endpoint and auto-saved on changes via debounced PUT.
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { useIcpTiers, useUpdateIcpTiers, type IcpTier } from '../../api/queries/usePlaybook'
import { useToast } from '../ui/Toast'

// ---------------------------------------------------------------------------
// Default empty tier
// ---------------------------------------------------------------------------

function newTier(index: number): IcpTier {
  return {
    name: `Tier ${index + 1}`,
    description: '',
    priority: index + 1,
    criteria: {
      industries: [],
      company_size_min: undefined,
      company_size_max: undefined,
      revenue_min: undefined,
      revenue_max: undefined,
      geographies: [],
      tech_signals: [],
      qualifying_signals: [],
    },
  }
}

// ---------------------------------------------------------------------------
// Tag input helper
// ---------------------------------------------------------------------------

function TagInput({
  values,
  onChange,
  placeholder,
}: {
  values: string[]
  onChange: (vals: string[]) => void
  placeholder: string
}) {
  const [input, setInput] = useState('')

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if ((e.key === 'Enter' || e.key === ',') && input.trim()) {
        e.preventDefault()
        const val = input.trim().replace(/,+$/, '')
        if (val && !values.includes(val)) {
          onChange([...values, val])
        }
        setInput('')
      }
      if (e.key === 'Backspace' && !input && values.length > 0) {
        onChange(values.slice(0, -1))
      }
    },
    [input, values, onChange],
  )

  const removeTag = useCallback(
    (idx: number) => {
      onChange(values.filter((_, i) => i !== idx))
    },
    [values, onChange],
  )

  return (
    <div className="flex flex-wrap gap-1.5 items-center min-h-[32px] px-2 py-1 rounded-md border border-border bg-surface-alt">
      {values.map((v, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-accent/10 text-accent"
        >
          {v}
          <button
            onClick={() => removeTag(i)}
            className="w-3 h-3 flex items-center justify-center rounded-full hover:bg-accent/20 transition-colors bg-transparent cursor-pointer border-0 text-accent/60 hover:text-accent text-[10px] leading-none"
            type="button"
          >
            x
          </button>
        </span>
      ))}
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={values.length === 0 ? placeholder : ''}
        className="flex-1 min-w-[80px] text-xs bg-transparent border-0 outline-none text-text placeholder:text-text-dim"
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tier Card
// ---------------------------------------------------------------------------

interface TierCardProps {
  tier: IcpTier
  index: number
  onChange: (updated: IcpTier) => void
  onDelete: () => void
}

function TierCard({ tier, index, onChange, onDelete }: TierCardProps) {
  const criteria = tier.criteria || {}

  const updateField = useCallback(
    <K extends keyof IcpTier>(key: K, value: IcpTier[K]) => {
      onChange({ ...tier, [key]: value })
    },
    [tier, onChange],
  )

  const updateCriteria = useCallback(
    (key: string, value: unknown) => {
      onChange({
        ...tier,
        criteria: { ...criteria, [key]: value },
      })
    },
    [tier, criteria, onChange],
  )

  const priorityColors = [
    'border-l-accent-cyan',
    'border-l-accent',
    'border-l-warning',
    'border-l-text-muted',
  ]
  const borderColor = priorityColors[Math.min(index, priorityColors.length - 1)]

  return (
    <div className={`bg-surface border border-border rounded-lg p-4 space-y-3 border-l-4 ${borderColor}`}>
      {/* Header row */}
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0 space-y-2">
          <input
            value={tier.name}
            onChange={(e) => updateField('name', e.target.value)}
            className="w-full text-sm font-semibold bg-transparent border-0 border-b border-transparent hover:border-border focus:border-accent outline-none text-text px-0 py-0.5 transition-colors"
            placeholder="Tier name..."
          />
          <textarea
            value={tier.description || ''}
            onChange={(e) => updateField('description', e.target.value)}
            className="w-full text-xs bg-transparent border-0 border-b border-transparent hover:border-border focus:border-accent outline-none text-text-muted px-0 py-0.5 resize-none transition-colors"
            placeholder="Description of this tier..."
            rows={2}
          />
        </div>
        <button
          onClick={onDelete}
          className="w-7 h-7 flex items-center justify-center rounded-md text-text-dim hover:text-error hover:bg-error/10 transition-colors bg-transparent cursor-pointer border-0 flex-shrink-0"
          title="Delete tier"
          type="button"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <path d="M3 3l8 8M11 3l-8 8" />
          </svg>
        </button>
      </div>

      {/* Criteria grid */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-[10px] font-medium text-text-dim uppercase tracking-wider mb-1">
            Industries
          </label>
          <TagInput
            values={criteria.industries || []}
            onChange={(vals) => updateCriteria('industries', vals)}
            placeholder="e.g., SaaS, FinTech..."
          />
        </div>
        <div>
          <label className="block text-[10px] font-medium text-text-dim uppercase tracking-wider mb-1">
            Geographies
          </label>
          <TagInput
            values={criteria.geographies || []}
            onChange={(vals) => updateCriteria('geographies', vals)}
            placeholder="e.g., DACH, US..."
          />
        </div>
        <div>
          <label className="block text-[10px] font-medium text-text-dim uppercase tracking-wider mb-1">
            Company Size (employees)
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={criteria.company_size_min ?? ''}
              onChange={(e) => updateCriteria('company_size_min', e.target.value ? Number(e.target.value) : undefined)}
              className="w-full px-2 py-1 text-xs rounded-md border border-border bg-surface-alt text-text placeholder:text-text-dim outline-none focus:ring-1 focus:ring-accent/40"
              placeholder="Min"
            />
            <span className="text-text-dim text-xs">-</span>
            <input
              type="number"
              value={criteria.company_size_max ?? ''}
              onChange={(e) => updateCriteria('company_size_max', e.target.value ? Number(e.target.value) : undefined)}
              className="w-full px-2 py-1 text-xs rounded-md border border-border bg-surface-alt text-text placeholder:text-text-dim outline-none focus:ring-1 focus:ring-accent/40"
              placeholder="Max"
            />
          </div>
        </div>
        <div>
          <label className="block text-[10px] font-medium text-text-dim uppercase tracking-wider mb-1">
            Revenue Range (EUR M)
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={criteria.revenue_min ?? ''}
              onChange={(e) => updateCriteria('revenue_min', e.target.value ? Number(e.target.value) : undefined)}
              className="w-full px-2 py-1 text-xs rounded-md border border-border bg-surface-alt text-text placeholder:text-text-dim outline-none focus:ring-1 focus:ring-accent/40"
              placeholder="Min"
            />
            <span className="text-text-dim text-xs">-</span>
            <input
              type="number"
              value={criteria.revenue_max ?? ''}
              onChange={(e) => updateCriteria('revenue_max', e.target.value ? Number(e.target.value) : undefined)}
              className="w-full px-2 py-1 text-xs rounded-md border border-border bg-surface-alt text-text placeholder:text-text-dim outline-none focus:ring-1 focus:ring-accent/40"
              placeholder="Max"
            />
          </div>
        </div>
        <div>
          <label className="block text-[10px] font-medium text-text-dim uppercase tracking-wider mb-1">
            Tech Signals
          </label>
          <TagInput
            values={criteria.tech_signals || []}
            onChange={(vals) => updateCriteria('tech_signals', vals)}
            placeholder="e.g., Kubernetes, React..."
          />
        </div>
        <div>
          <label className="block text-[10px] font-medium text-text-dim uppercase tracking-wider mb-1">
            Qualifying Signals
          </label>
          <TagInput
            values={criteria.qualifying_signals || []}
            onChange={(vals) => updateCriteria('qualifying_signals', vals)}
            placeholder="e.g., Series B, hiring..."
          />
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty State
// ---------------------------------------------------------------------------

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <div className="w-14 h-14 rounded-2xl bg-accent-cyan/10 flex items-center justify-center mb-4">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-accent-cyan">
          <path d="M3 6h18M3 12h18M3 18h18" strokeLinecap="round" />
        </svg>
      </div>
      <h3 className="text-sm font-semibold text-text mb-1">No ICP tiers defined yet</h3>
      <p className="text-xs text-text-muted max-w-sm mb-4">
        Define your ideal customer profile tiers with structured criteria.
        The AI can also extract these from your strategy document.
      </p>
      <button
        onClick={onAdd}
        className="px-4 py-2 text-xs font-medium rounded-md bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/30 hover:bg-accent-cyan/20 transition-colors cursor-pointer"
        type="button"
      >
        Add First Tier
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function IcpTiersTab() {
  const { toast } = useToast()
  const tiersQuery = useIcpTiers()
  const updateMutation = useUpdateIcpTiers()

  const [localTiers, setLocalTiers] = useState<IcpTier[] | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Sync server data to local state on first load
  useEffect(() => {
    if (tiersQuery.data && localTiers === null) {
      setLocalTiers(tiersQuery.data.tiers)
    }
  }, [tiersQuery.data, localTiers])

  // Debounced save
  const saveTiers = useCallback(
    (tiers: IcpTier[]) => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        updateMutation.mutate(tiers, {
          onError: () => toast('Failed to save tiers', 'error'),
        })
      }, 1000)
    },
    [updateMutation, toast],
  )

  // Cleanup
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  const tiers = localTiers ?? tiersQuery.data?.tiers ?? []

  const updateTier = useCallback(
    (index: number, updated: IcpTier) => {
      const next = [...tiers]
      next[index] = updated
      setLocalTiers(next)
      saveTiers(next)
    },
    [tiers, saveTiers],
  )

  const deleteTier = useCallback(
    (index: number) => {
      const next = tiers.filter((_, i) => i !== index)
      setLocalTiers(next)
      saveTiers(next)
      toast('Tier removed', 'info')
    },
    [tiers, saveTiers, toast],
  )

  const addTier = useCallback(() => {
    const next = [...tiers, newTier(tiers.length)]
    setLocalTiers(next)
    saveTiers(next)
  }, [tiers, saveTiers])

  // Loading state
  if (tiersQuery.isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-6 h-6 border-2 border-border border-t-accent rounded-full animate-spin" />
      </div>
    )
  }

  // Empty state
  if (tiers.length === 0) {
    return <EmptyState onAdd={addTier} />
  }

  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
      <div className="p-4 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-text">ICP Tiers</h2>
            <p className="text-xs text-text-muted">
              {tiers.length} tier{tiers.length !== 1 ? 's' : ''} defined
              {updateMutation.isPending && (
                <span className="ml-2 text-text-dim animate-pulse">Saving...</span>
              )}
            </p>
          </div>
          <button
            onClick={addTier}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/30 hover:bg-accent-cyan/20 transition-colors cursor-pointer"
            type="button"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M6 2v8M2 6h8" />
            </svg>
            Add Tier
          </button>
        </div>

        {/* Tier cards */}
        {tiers.map((tier, idx) => (
          <TierCard
            key={idx}
            tier={tier}
            index={idx}
            onChange={(updated) => updateTier(idx, updated)}
            onDelete={() => deleteTier(idx)}
          />
        ))}
      </div>
    </div>
  )
}
