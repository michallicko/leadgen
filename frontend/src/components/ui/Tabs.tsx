export interface Tab {
  id: string
  label: string
  badge?: number | string
  disabled?: boolean
}

interface TabsProps {
  tabs: Tab[]
  activeTab: string
  onChange: (tabId: string) => void
}

export function Tabs({ tabs, activeTab, onChange }: TabsProps) {
  return (
    <div className="flex border-b border-border">
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab
        return (
          <button
            key={tab.id}
            onClick={() => !tab.disabled && onChange(tab.id)}
            disabled={tab.disabled}
            className={`
              relative px-4 py-2.5 text-sm font-medium transition-colors border-none bg-transparent cursor-pointer
              ${isActive
                ? 'text-accent-cyan'
                : tab.disabled
                  ? 'text-text-dim opacity-50 cursor-not-allowed'
                  : 'text-text-muted hover:text-text'
              }
            `}
          >
            <span className="flex items-center gap-2">
              {tab.label}
              {tab.badge !== undefined && (
                <span className={`
                  text-[11px] px-1.5 py-0 rounded-full tabular-nums
                  ${isActive
                    ? 'bg-accent-cyan/15 text-accent-cyan'
                    : 'bg-surface-alt text-text-dim'
                  }
                `}>
                  {tab.badge}
                </span>
              )}
            </span>
            {isActive && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent-cyan rounded-full" />
            )}
          </button>
        )
      })}
    </div>
  )
}
