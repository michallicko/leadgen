import { useState, type ReactNode } from 'react'

export interface TabDef {
  id: string
  label: string
  count?: number
  content: ReactNode
}

/** Lightweight tab descriptor (no content — used when parent manages panels). */
export interface Tab {
  id: string
  label: string
  badge?: number
  disabled?: boolean
}

interface SelfManagedProps {
  tabs: TabDef[]
  defaultTab?: string
  activeTab?: undefined
  onChange?: undefined
}

interface ExternallyManagedProps {
  tabs: Tab[]
  activeTab: string
  onChange: (tabId: string) => void
  defaultTab?: undefined
}

type TabsProps = SelfManagedProps | ExternallyManagedProps

export function Tabs(props: TabsProps) {
  const { tabs } = props
  const [internalId, setInternalId] = useState(
    props.activeTab ?? ('defaultTab' in props ? props.defaultTab : undefined) ?? tabs[0]?.id ?? '',
  )

  const isExternal = props.activeTab !== undefined
  const activeId = isExternal ? props.activeTab : internalId

  const handleClick = (id: string) => {
    if (isExternal && props.onChange) {
      props.onChange(id)
    } else {
      setInternalId(id)
    }
  }

  // Fall back to first tab if active tab no longer exists
  const effectiveId = tabs.find((t) => t.id === activeId) ? activeId : (tabs[0]?.id ?? '')

  return (
    <div>
      {/* Tab bar */}
      <div className="sticky top-0 z-10 bg-bg">
        <div className="flex border-b border-border-solid overflow-x-auto scrollbar-hide">
          {tabs.map((tab) => {
            const isDisabled = 'disabled' in tab && tab.disabled
            const badge = 'badge' in tab ? tab.badge : ('count' in tab ? tab.count : undefined)
            return (
              <button
                key={tab.id}
                onClick={() => !isDisabled && handleClick(tab.id)}
                disabled={!!isDisabled}
                className={`flex-shrink-0 px-4 py-2.5 text-xs font-semibold uppercase tracking-wider border-b-2 transition-colors whitespace-nowrap ${
                  isDisabled
                    ? 'border-transparent text-text-dim cursor-not-allowed opacity-50'
                    : effectiveId === tab.id
                      ? 'border-accent-cyan text-text'
                      : 'border-transparent text-text-muted hover:text-text'
                }`}
              >
                {tab.label}
                {badge != null && badge > 0 && (
                  <span className={`ml-1.5 ${effectiveId === tab.id ? 'text-accent-cyan' : 'text-text-dim'}`}>
                    {badge}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Tab panels — only for self-managed tabs with content */}
      {!isExternal && (tabs as TabDef[]).map((tab) => (
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
