/**
 * ConfigManager — dropdown for saving, loading, and managing enrichment configs.
 * Appears in the DagControls bar during configure mode.
 */

import { useState, useRef, useEffect } from 'react'
import {
  useEnrichConfigs,
  useSaveConfig,
  useUpdateConfig,
  useDeleteConfig,
  type EnrichConfigData,
} from '../../api/queries/useEnrichConfigs'

interface ConfigManagerProps {
  onLoad: (config: Record<string, unknown>) => void
  getSnapshot: () => Record<string, unknown>
}

export function ConfigManager({ onLoad, getSnapshot }: ConfigManagerProps) {
  const { data: configs, isLoading } = useEnrichConfigs()
  const saveConfig = useSaveConfig()
  const updateConfig = useUpdateConfig()
  const deleteConfig = useDeleteConfig()

  const [isOpen, setIsOpen] = useState(false)
  const [showSave, setShowSave] = useState(false)
  const [saveName, setSaveName] = useState('')
  const [saveDesc, setSaveDesc] = useState('')
  const menuRef = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false)
        setShowSave(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const handleSave = () => {
    if (!saveName.trim()) return
    saveConfig.mutate(
      { name: saveName.trim(), description: saveDesc.trim(), config: getSnapshot() },
      {
        onSuccess: () => {
          setSaveName('')
          setSaveDesc('')
          setShowSave(false)
        },
      },
    )
  }

  const handleOverwrite = (cfg: EnrichConfigData) => {
    updateConfig.mutate({ id: cfg.id, config: getSnapshot() })
  }

  const handleLoad = (cfg: EnrichConfigData) => {
    onLoad(cfg.config)
    setIsOpen(false)
  }

  const handleDelete = (cfg: EnrichConfigData) => {
    if (confirm(`Delete "${cfg.name}"?`)) {
      deleteConfig.mutate(cfg.id)
    }
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => { setIsOpen(!isOpen); setShowSave(false) }}
        className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-border text-text-muted hover:text-text hover:border-accent/40 transition-colors"
      >
        <span className="text-xs">&#9881;</span>
        Configs
        {configs && configs.length > 0 && (
          <span className="text-[0.6rem] bg-surface-alt px-1 rounded">{configs.length}</span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-1 w-72 bg-surface border border-border rounded-lg shadow-lg z-50 overflow-hidden">
          {/* Save new */}
          <div className="p-2 border-b border-border">
            {!showSave ? (
              <button
                onClick={() => setShowSave(true)}
                className="w-full text-left px-2 py-1.5 text-sm text-accent hover:bg-surface-alt rounded transition-colors"
              >
                + Save current config...
              </button>
            ) : (
              <div className="space-y-1.5">
                <input
                  type="text"
                  value={saveName}
                  onChange={(e) => setSaveName(e.target.value)}
                  placeholder="Config name"
                  className="w-full px-2 py-1 text-sm rounded border border-border bg-surface-alt text-text focus:border-accent focus:outline-none"
                  autoFocus
                  onKeyDown={(e) => e.key === 'Enter' && handleSave()}
                />
                <input
                  type="text"
                  value={saveDesc}
                  onChange={(e) => setSaveDesc(e.target.value)}
                  placeholder="Description (optional)"
                  className="w-full px-2 py-1 text-sm rounded border border-border bg-surface-alt text-text focus:border-accent focus:outline-none"
                />
                <div className="flex justify-end gap-1">
                  <button
                    onClick={() => setShowSave(false)}
                    className="px-2 py-0.5 text-xs text-text-muted hover:text-text"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={!saveName.trim() || saveConfig.isPending}
                    className="px-2 py-0.5 text-xs bg-accent text-white rounded disabled:opacity-40"
                  >
                    {saveConfig.isPending ? 'Saving...' : 'Save'}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Saved configs list */}
          <div className="max-h-64 overflow-y-auto">
            {isLoading && (
              <p className="p-3 text-xs text-text-dim text-center">Loading...</p>
            )}
            {!isLoading && (!configs || configs.length === 0) && (
              <p className="p-3 text-xs text-text-dim text-center">No saved configs</p>
            )}
            {configs?.map((cfg) => (
              <div
                key={cfg.id}
                className="flex items-center justify-between px-3 py-2 hover:bg-surface-alt border-b border-border last:border-b-0 group"
              >
                <button
                  onClick={() => handleLoad(cfg)}
                  className="flex-1 text-left"
                  title={cfg.description || undefined}
                >
                  <span className="text-sm text-text font-medium">{cfg.name}</span>
                  {cfg.is_default && (
                    <span className="ml-1.5 text-[0.6rem] text-accent bg-accent/10 px-1 rounded">default</span>
                  )}
                  {cfg.description && (
                    <p className="text-[0.6rem] text-text-dim truncate">{cfg.description}</p>
                  )}
                </button>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => handleOverwrite(cfg)}
                    className="p-1 text-xs text-text-muted hover:text-accent"
                    title="Overwrite with current settings"
                  >
                    &#8635;
                  </button>
                  <button
                    onClick={() => handleDelete(cfg)}
                    className="p-1 text-xs text-text-muted hover:text-error"
                    title="Delete"
                  >
                    &#10005;
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
