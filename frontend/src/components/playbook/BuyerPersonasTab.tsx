/**
 * BuyerPersonasTab -- structured buyer persona cards with inline editing.
 *
 * Each persona renders as a card with name, role, seniority, pain points,
 * goals, preferred channels, messaging hooks, objections, and linked tiers.
 *
 * Data is stored in extracted_data.personas via the
 * /api/playbook/strategy/personas endpoint and auto-saved via debounced PUT.
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import {
  useBuyerPersonas,
  useUpdateBuyerPersonas,
  useIcpTiers,
  type BuyerPersona,
} from '../../api/queries/usePlaybook'
import { useToast } from '../ui/Toast'

// ---------------------------------------------------------------------------
// Default empty persona
// ---------------------------------------------------------------------------

function newPersona(): BuyerPersona {
  return {
    name: '',
    role: '',
    seniority: '',
    pain_points: [],
    goals: [],
    preferred_channels: [],
    messaging_hooks: [],
    objections: [],
    linked_tiers: [],
  }
}

// ---------------------------------------------------------------------------
// Tag input helper (reused from IcpTiersTab pattern)
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
// Channel checkboxes
// ---------------------------------------------------------------------------

const CHANNEL_OPTIONS = ['LinkedIn', 'Email', 'Phone', 'Twitter/X', 'Events', 'Referral']

function ChannelCheckboxes({
  selected,
  onChange,
}: {
  selected: string[]
  onChange: (channels: string[]) => void
}) {
  const toggle = useCallback(
    (channel: string) => {
      if (selected.includes(channel)) {
        onChange(selected.filter((c) => c !== channel))
      } else {
        onChange([...selected, channel])
      }
    },
    [selected, onChange],
  )

  return (
    <div className="flex flex-wrap gap-2">
      {CHANNEL_OPTIONS.map((ch) => (
        <label
          key={ch}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-full cursor-pointer border transition-colors ${
            selected.includes(ch)
              ? 'bg-accent/10 text-accent border-accent/30'
              : 'bg-surface-alt text-text-muted border-border hover:border-border-solid'
          }`}
        >
          <input
            type="checkbox"
            checked={selected.includes(ch)}
            onChange={() => toggle(ch)}
            className="sr-only"
          />
          {ch}
        </label>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tier multi-select
// ---------------------------------------------------------------------------

function TierMultiSelect({
  selected,
  onChange,
  availableTiers,
}: {
  selected: string[]
  onChange: (tiers: string[]) => void
  availableTiers: string[]
}) {
  const toggle = useCallback(
    (tier: string) => {
      if (selected.includes(tier)) {
        onChange(selected.filter((t) => t !== tier))
      } else {
        onChange([...selected, tier])
      }
    },
    [selected, onChange],
  )

  if (availableTiers.length === 0) {
    return (
      <p className="text-xs text-text-dim italic">
        No ICP tiers defined yet. Add tiers in the ICP Tiers tab first.
      </p>
    )
  }

  return (
    <div className="flex flex-wrap gap-2">
      {availableTiers.map((tier) => (
        <label
          key={tier}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-full cursor-pointer border transition-colors ${
            selected.includes(tier)
              ? 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/30'
              : 'bg-surface-alt text-text-muted border-border hover:border-border-solid'
          }`}
        >
          <input
            type="checkbox"
            checked={selected.includes(tier)}
            onChange={() => toggle(tier)}
            className="sr-only"
          />
          {tier}
        </label>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Persona Card
// ---------------------------------------------------------------------------

interface PersonaCardProps {
  persona: BuyerPersona
  onChange: (updated: BuyerPersona) => void
  onDelete: () => void
  availableTiers: string[]
}

function PersonaCard({ persona, onChange, onDelete, availableTiers }: PersonaCardProps) {
  const update = useCallback(
    <K extends keyof BuyerPersona>(key: K, value: BuyerPersona[K]) => {
      onChange({ ...persona, [key]: value })
    },
    [persona, onChange],
  )

  return (
    <div className="bg-surface border border-border rounded-lg p-4 space-y-3">
      {/* Header */}
      <div className="flex items-start gap-3">
        {/* Avatar placeholder */}
        <div className="w-10 h-10 rounded-full bg-accent/10 flex items-center justify-center flex-shrink-0 text-accent text-sm font-semibold">
          {persona.name ? persona.name[0].toUpperCase() : '?'}
        </div>
        <div className="flex-1 min-w-0 space-y-1">
          <input
            value={persona.name}
            onChange={(e) => update('name', e.target.value)}
            className="w-full text-sm font-semibold bg-transparent border-0 border-b border-transparent hover:border-border focus:border-accent outline-none text-text px-0 py-0.5 transition-colors"
            placeholder="Persona name..."
          />
          <div className="flex gap-3">
            <input
              value={persona.role || ''}
              onChange={(e) => update('role', e.target.value)}
              className="flex-1 text-xs bg-transparent border-0 border-b border-transparent hover:border-border focus:border-accent outline-none text-text-muted px-0 py-0.5 transition-colors"
              placeholder="Role / title pattern..."
            />
            <input
              value={persona.seniority || ''}
              onChange={(e) => update('seniority', e.target.value)}
              className="w-28 text-xs bg-transparent border-0 border-b border-transparent hover:border-border focus:border-accent outline-none text-text-muted px-0 py-0.5 transition-colors"
              placeholder="Seniority..."
            />
          </div>
        </div>
        <button
          onClick={onDelete}
          className="w-7 h-7 flex items-center justify-center rounded-md text-text-dim hover:text-error hover:bg-error/10 transition-colors bg-transparent cursor-pointer border-0 flex-shrink-0"
          title="Delete persona"
          type="button"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <path d="M3 3l8 8M11 3l-8 8" />
          </svg>
        </button>
      </div>

      {/* Pain Points */}
      <div>
        <label className="block text-[10px] font-medium text-text-dim uppercase tracking-wider mb-1">
          Pain Points
        </label>
        <TagInput
          values={persona.pain_points || []}
          onChange={(vals) => update('pain_points', vals)}
          placeholder="e.g., Slow lead qualification..."
        />
      </div>

      {/* Goals */}
      <div>
        <label className="block text-[10px] font-medium text-text-dim uppercase tracking-wider mb-1">
          Goals
        </label>
        <TagInput
          values={persona.goals || []}
          onChange={(vals) => update('goals', vals)}
          placeholder="e.g., Scale outbound pipeline..."
        />
      </div>

      {/* Preferred Channels */}
      <div>
        <label className="block text-[10px] font-medium text-text-dim uppercase tracking-wider mb-1">
          Preferred Channels
        </label>
        <ChannelCheckboxes
          selected={persona.preferred_channels || []}
          onChange={(channels) => update('preferred_channels', channels)}
        />
      </div>

      {/* Messaging Hooks */}
      <div>
        <label className="block text-[10px] font-medium text-text-dim uppercase tracking-wider mb-1">
          Messaging Hooks
        </label>
        <TagInput
          values={persona.messaging_hooks || []}
          onChange={(vals) => update('messaging_hooks', vals)}
          placeholder="e.g., ROI in 90 days..."
        />
      </div>

      {/* Objections */}
      <div>
        <label className="block text-[10px] font-medium text-text-dim uppercase tracking-wider mb-1">
          Common Objections
        </label>
        <TagInput
          values={persona.objections || []}
          onChange={(vals) => update('objections', vals)}
          placeholder="e.g., Already have a solution..."
        />
      </div>

      {/* Linked Tiers */}
      <div>
        <label className="block text-[10px] font-medium text-text-dim uppercase tracking-wider mb-1">
          Linked ICP Tiers
        </label>
        <TierMultiSelect
          selected={persona.linked_tiers || []}
          onChange={(tiers) => update('linked_tiers', tiers)}
          availableTiers={availableTiers}
        />
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
      <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mb-4">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-accent">
          <circle cx="12" cy="8" r="4" />
          <path d="M5 20v-1a7 7 0 0 1 14 0v1" />
        </svg>
      </div>
      <h3 className="text-sm font-semibold text-text mb-1">No buyer personas defined yet</h3>
      <p className="text-xs text-text-muted max-w-sm mb-4">
        Define your target buyer personas with structured fields for
        personalized messaging. The AI can also generate these from your strategy.
      </p>
      <button
        onClick={onAdd}
        className="px-4 py-2 text-xs font-medium rounded-md bg-accent/10 text-accent border border-accent/30 hover:bg-accent/20 transition-colors cursor-pointer"
        type="button"
      >
        Add First Persona
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function BuyerPersonasTab() {
  const { toast } = useToast()
  const personasQuery = useBuyerPersonas()
  const updateMutation = useUpdateBuyerPersonas()
  const tiersQuery = useIcpTiers()

  const [localPersonas, setLocalPersonas] = useState<BuyerPersona[] | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Sync server data to local state on first load
  useEffect(() => {
    if (personasQuery.data && localPersonas === null) {
      setLocalPersonas(personasQuery.data.personas)
    }
  }, [personasQuery.data, localPersonas])

  // Debounced save
  const savePersonas = useCallback(
    (personas: BuyerPersona[]) => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        updateMutation.mutate(personas, {
          onError: () => toast('Failed to save personas', 'error'),
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

  const personas = localPersonas ?? personasQuery.data?.personas ?? []
  const availableTiers = (tiersQuery.data?.tiers ?? []).map((t) => t.name).filter(Boolean)

  const updatePersona = useCallback(
    (index: number, updated: BuyerPersona) => {
      const next = [...personas]
      next[index] = updated
      setLocalPersonas(next)
      savePersonas(next)
    },
    [personas, savePersonas],
  )

  const deletePersona = useCallback(
    (index: number) => {
      const next = personas.filter((_, i) => i !== index)
      setLocalPersonas(next)
      savePersonas(next)
      toast('Persona removed', 'info')
    },
    [personas, savePersonas, toast],
  )

  const addPersona = useCallback(() => {
    const next = [...personas, newPersona()]
    setLocalPersonas(next)
    savePersonas(next)
  }, [personas, savePersonas])

  // Loading state
  if (personasQuery.isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-6 h-6 border-2 border-border border-t-accent rounded-full animate-spin" />
      </div>
    )
  }

  // Empty state
  if (personas.length === 0) {
    return <EmptyState onAdd={addPersona} />
  }

  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
      <div className="p-4 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-text">Buyer Personas</h2>
            <p className="text-xs text-text-muted">
              {personas.length} persona{personas.length !== 1 ? 's' : ''} defined
              {updateMutation.isPending && (
                <span className="ml-2 text-text-dim animate-pulse">Saving...</span>
              )}
            </p>
          </div>
          <button
            onClick={addPersona}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-accent/10 text-accent border border-accent/30 hover:bg-accent/20 transition-colors cursor-pointer"
            type="button"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M6 2v8M2 6h8" />
            </svg>
            Add Persona
          </button>
        </div>

        {/* Persona cards */}
        {personas.map((persona, idx) => (
          <PersonaCard
            key={idx}
            persona={persona}
            onChange={(updated) => updatePersona(idx, updated)}
            onDelete={() => deletePersona(idx)}
            availableTiers={availableTiers}
          />
        ))}
      </div>
    </div>
  )
}
