import { useState, type ReactNode } from 'react'

export interface TabDef {
  id: string
  label: string
  count?: number
  content: ReactNode
}

interface TabsProps {
  tabs: TabDef[]
  defaultTab?: string
}

export function Tabs({ tabs, defaultTab }: TabsProps) {
  const [activeId, setActiveId] = useState(defaultTab ?? tabs[0]?.id ?? '')

  // Fall back to first tab if active tab no longer exists (conditional tabs)
  const effectiveId = tabs.find((t) => t.id === activeId) ? activeId : (tabs[0]?.id ?? '')

  return (
    <div>
      {/* Tab bar — sticky within scroll container, horizontally scrollable on small screens */}
      <div className="sticky top-0 z-10 bg-bg">
        <div className="flex border-b border-border-solid overflow-x-auto scrollbar-hide">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveId(tab.id)}
              className={`flex-shrink-0 px-4 py-2.5 text-xs font-semibold uppercase tracking-wider border-b-2 transition-colors whitespace-nowrap ${
                effectiveId === tab.id
                  ? 'border-accent-cyan text-text'
                  : 'border-transparent text-text-muted hover:text-text'
              }`}
            >
              {tab.label}
              {tab.count != null && tab.count > 0 && (
                <span className={`ml-1.5 ${effectiveId === tab.id ? 'text-accent-cyan' : 'text-text-dim'}`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Tab panels — all rendered, only active is visible (preserves form state) */}
      {tabs.map((tab) => (
        <div
          key={tab.id}
          className={tab.id === effectiveId ? 'pt-5' : 'hidden'}
        >
          {tab.content}
        </div>
      ))}
    </div>
  )
}
