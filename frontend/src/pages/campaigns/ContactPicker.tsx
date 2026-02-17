import { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { apiFetch } from '../../api/client'

interface PickerContact {
  id: string
  full_name: string
  job_title: string | null
  company_name: string | null
  email_address: string | null
  contact_score: number | null
}

interface Props {
  campaignId: string
  existingContactIds: string[]
  onAdd: (contactIds: string[]) => void
  onClose: () => void
  isLoading: boolean
}

export function ContactPicker({ existingContactIds, onAdd, onClose, isLoading }: Props) {
  const [search, setSearch] = useState('')
  const [contacts, setContacts] = useState<PickerContact[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const overlayRef = useRef<HTMLDivElement>(null)

  // Fetch contacts on mount
  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const data = await apiFetch<{ contacts: PickerContact[]; total: number }>('/contacts', {
          params: { page_size: '200' },
        })
        if (!cancelled) {
          setContacts(data.contacts)
          setLoading(false)
        }
      } catch {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  // Escape key closes
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  const existingSet = useMemo(() => new Set(existingContactIds), [existingContactIds])

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return contacts
      .filter((c) => !existingSet.has(c.id))
      .filter((c) =>
        !q ||
        c.full_name.toLowerCase().includes(q) ||
        (c.company_name || '').toLowerCase().includes(q) ||
        (c.job_title || '').toLowerCase().includes(q) ||
        (c.email_address || '').toLowerCase().includes(q),
      )
  }, [contacts, search, existingSet])

  const toggleSelect = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const selectAll = useCallback(() => {
    setSelected(new Set(filtered.map((c) => c.id)))
  }, [filtered])

  const clearSelection = useCallback(() => {
    setSelected(new Set())
  }, [])

  const handleAdd = useCallback(() => {
    onAdd(Array.from(selected))
  }, [selected, onAdd])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        ref={overlayRef}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl max-h-[80vh] bg-surface border border-border rounded-lg shadow-xl flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h3 className="text-sm font-semibold text-text">Add Contacts to Campaign</h3>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text text-lg bg-transparent border-none cursor-pointer leading-none"
          >
            &times;
          </button>
        </div>

        {/* Search */}
        <div className="px-4 py-2 border-b border-border">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search contacts..."
            className="w-full px-3 py-1.5 text-sm rounded border border-border bg-surface text-text outline-none focus:border-accent"
            autoFocus
          />
        </div>

        {/* Selection controls */}
        <div className="flex items-center justify-between px-4 py-1.5 text-xs text-text-muted border-b border-border/50">
          <span>{filtered.length} available &middot; {selected.size} selected</span>
          <div className="flex gap-2">
            <button onClick={selectAll} className="text-accent-cyan hover:underline bg-transparent border-none cursor-pointer text-xs p-0">
              Select all
            </button>
            {selected.size > 0 && (
              <button onClick={clearSelection} className="text-text-muted hover:text-text bg-transparent border-none cursor-pointer text-xs p-0">
                Clear
              </button>
            )}
          </div>
        </div>

        {/* Contact list */}
        <div className="flex-1 overflow-y-auto min-h-0">
          {loading ? (
            <p className="text-xs text-text-muted p-4">Loading contacts...</p>
          ) : filtered.length === 0 ? (
            <p className="text-xs text-text-muted p-4">
              {search ? 'No matching contacts found.' : 'All contacts are already assigned.'}
            </p>
          ) : (
            <table className="w-full text-sm">
              <tbody>
                {filtered.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => toggleSelect(c.id)}
                    className={`cursor-pointer border-b border-border/30 transition-colors ${
                      selected.has(c.id) ? 'bg-accent/5' : 'hover:bg-surface-alt'
                    }`}
                  >
                    <td className="px-4 py-2 w-8">
                      <span
                        className={`inline-flex w-4 h-4 rounded border items-center justify-center text-[10px] transition-colors ${
                          selected.has(c.id)
                            ? 'bg-accent border-accent text-white'
                            : 'bg-transparent border-[#8B92A0]/40'
                        }`}
                      >
                        {selected.has(c.id) ? '\u2713' : ''}
                      </span>
                    </td>
                    <td className="py-2 text-text font-medium">{c.full_name}</td>
                    <td className="py-2 text-text-muted text-xs">{c.job_title || '-'}</td>
                    <td className="py-2 text-text-muted text-xs">{c.company_name || '-'}</td>
                    <td className="py-2 pr-4 text-text-dim text-xs tabular-nums">
                      {c.contact_score ?? '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-border">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm rounded bg-transparent text-text-muted border border-border cursor-pointer hover:text-text transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleAdd}
            disabled={selected.size === 0 || isLoading}
            className="px-4 py-1.5 text-sm font-medium rounded bg-accent text-white border-none cursor-pointer hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Adding...' : `Add ${selected.size} Contact${selected.size !== 1 ? 's' : ''}`}
          </button>
        </div>
      </div>
    </div>
  )
}
