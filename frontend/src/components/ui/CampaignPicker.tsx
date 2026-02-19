import { useState, useMemo } from 'react'
import { useCampaigns, type Campaign } from '../../api/queries/useCampaigns'

interface CampaignPickerProps {
  onConfirm: (campaignId: string) => void
  onClose: () => void
  isLoading?: boolean
}

export function CampaignPicker({ onConfirm, onClose, isLoading }: CampaignPickerProps) {
  const { data: campaignsData } = useCampaigns()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  const campaigns = useMemo(() => {
    const all = campaignsData?.campaigns ?? []
    const q = search.toLowerCase()
    if (!q) return all
    return all.filter((c) => c.name.toLowerCase().includes(q))
  }, [campaignsData, search])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-surface border border-border-solid rounded-xl shadow-xl w-96 max-h-[70vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b border-border-solid">
          <h3 className="text-sm font-semibold text-text">Assign to Campaign</h3>
          <p className="text-xs text-text-muted mt-0.5">Select a campaign to add selected entities to</p>
        </div>

        <div className="px-3 py-2 border-b border-border-solid">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search campaigns..."
            className="w-full px-2 py-1.5 text-xs bg-surface-alt border border-border-solid rounded text-text placeholder:text-text-muted outline-none focus:border-accent"
            autoFocus
          />
        </div>

        <div className="flex-1 overflow-auto px-2 py-2 min-h-0">
          {campaigns.map((c: Campaign) => (
            <label
              key={c.id}
              className={`flex items-center gap-3 px-2 py-2 rounded cursor-pointer transition-colors ${
                selectedId === c.id ? 'bg-accent/10' : 'hover:bg-surface-alt'
              }`}
            >
              <input
                type="radio"
                name="campaign"
                checked={selectedId === c.id}
                onChange={() => setSelectedId(c.id)}
                className="w-4 h-4 accent-accent cursor-pointer"
              />
              <div className="flex-1 min-w-0">
                <span className="text-sm text-text block truncate">{c.name}</span>
                <span className="text-[11px] text-text-muted">
                  {c.status} &middot; {c.total_contacts} contacts
                </span>
              </div>
            </label>
          ))}
          {campaigns.length === 0 && (
            <p className="text-xs text-text-muted px-2 py-2">
              {search ? 'No campaigns match your search.' : 'No campaigns available.'}
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-border-solid">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-xs text-text-muted hover:text-text bg-transparent border-none cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={() => selectedId && onConfirm(selectedId)}
            disabled={!selectedId || isLoading}
            className="px-4 py-1.5 text-xs font-medium rounded-lg bg-accent text-white border-none cursor-pointer hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Assigning...' : 'Assign'}
          </button>
        </div>
      </div>
    </div>
  )
}
