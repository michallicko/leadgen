import { useState, useMemo, useCallback } from 'react'
import { useTags, type Tag } from '../../api/queries/useTags'
import { apiFetch } from '../../api/client'
import { useQueryClient } from '@tanstack/react-query'

interface TagPickerProps {
  onConfirm: (tagIds: string[]) => void
  onClose: () => void
  isLoading?: boolean
}

export function TagPicker({ onConfirm, onClose, isLoading }: TagPickerProps) {
  const { data: tagsData } = useTags()
  const qc = useQueryClient()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [newTagName, setNewTagName] = useState('')
  const [creating, setCreating] = useState(false)

  const tags = useMemo(() => tagsData?.tags ?? [], [tagsData])

  const toggleTag = useCallback((tagId: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(tagId)) next.delete(tagId)
      else next.add(tagId)
      return next
    })
  }, [])

  const handleCreateTag = useCallback(async () => {
    const name = newTagName.trim()
    if (!name) return
    setCreating(true)
    try {
      const result = await apiFetch<{ id: string; name: string }>('/tags', {
        method: 'POST',
        body: { name },
      })
      qc.invalidateQueries({ queryKey: ['tags'] })
      setSelected((prev) => new Set(prev).add(result.id))
      setNewTagName('')
    } catch {
      // tag creation failed silently
    } finally {
      setCreating(false)
    }
  }, [newTagName, qc])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-surface border border-border-solid rounded-xl shadow-xl w-80 max-h-96 flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b border-border-solid">
          <h3 className="text-sm font-semibold text-text">Add Tags</h3>
          <p className="text-xs text-text-muted mt-0.5">Select tags to add to selected entities</p>
        </div>

        <div className="flex-1 overflow-auto px-2 py-2">
          {tags.map((tag: Tag) => (
            <label
              key={tag.id}
              className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-alt cursor-pointer"
            >
              <input
                type="checkbox"
                checked={selected.has(tag.id)}
                onChange={() => toggleTag(tag.id)}
                className="w-4 h-4 accent-accent cursor-pointer"
              />
              <span className="text-sm text-text">{tag.name}</span>
            </label>
          ))}
          {tags.length === 0 && (
            <p className="text-xs text-text-muted px-2 py-2">No tags available</p>
          )}
        </div>

        <div className="px-3 py-2 border-t border-border-solid">
          <div className="flex gap-2">
            <input
              type="text"
              value={newTagName}
              onChange={(e) => setNewTagName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreateTag()}
              placeholder="New tag name..."
              className="flex-1 px-2 py-1 text-xs bg-surface-alt border border-border-solid rounded text-text placeholder:text-text-muted outline-none focus:border-accent"
            />
            <button
              onClick={handleCreateTag}
              disabled={!newTagName.trim() || creating}
              className="px-2 py-1 text-xs font-medium rounded bg-surface-alt hover:bg-accent/10 text-text border border-border-solid cursor-pointer disabled:opacity-50"
            >
              {creating ? '...' : 'Create'}
            </button>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-border-solid">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-xs text-text-muted hover:text-text bg-transparent border-none cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(Array.from(selected))}
            disabled={selected.size === 0 || isLoading}
            className="px-4 py-1.5 text-xs font-medium rounded-lg bg-accent text-white border-none cursor-pointer hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Adding...' : `Add ${selected.size} Tag${selected.size !== 1 ? 's' : ''}`}
          </button>
        </div>
      </div>
    </div>
  )
}
