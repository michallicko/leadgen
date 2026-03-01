/**
 * TemplateSelector -- 2-column card grid for selecting a strategy template.
 *
 * Used in the onboarding flow between discovery questions and AI draft generation.
 * Shows system templates + user templates + a "Blank slate" option.
 */

import { useState } from 'react'
import {
  useStrategyTemplates,
  type StrategyTemplate,
} from '../../api/queries/useStrategyTemplates'

interface TemplateSelectorProps {
  onSelect: (templateId: string | null) => void
  onBack: () => void
  isApplying: boolean
}

function ExpandIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`transition-transform ${expanded ? 'rotate-180' : ''}`}
    >
      <path d="M4 6l4 4 4-4" />
    </svg>
  )
}

function CategoryBadge({ category }: { category: string }) {
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded bg-accent-cyan/10 text-accent-cyan">
      {category}
    </span>
  )
}

function TemplateCard({
  template,
  isSelected,
  onSelect,
}: {
  template: StrategyTemplate
  isSelected: boolean
  onSelect: () => void
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className={`
        border rounded-lg p-4 cursor-pointer transition-all
        ${isSelected
          ? 'border-accent bg-accent/5 ring-1 ring-accent/20'
          : 'border-border hover:border-border-solid hover:bg-surface-alt/30'
        }
      `}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect() } }}
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <h3 className="text-sm font-semibold text-text">{template.name}</h3>
        {template.category && <CategoryBadge category={template.category} />}
      </div>

      {template.description && (
        <p className="text-xs text-text-muted line-clamp-2 mb-2">
          {template.description}
        </p>
      )}

      {template.section_headers.length > 0 && (
        <button
          onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}
          className="flex items-center gap-1 text-[10px] text-text-dim hover:text-text-muted transition-colors bg-transparent border-none cursor-pointer p-0"
        >
          <ExpandIcon expanded={expanded} />
          {expanded ? 'Hide sections' : `${template.section_headers.length} sections`}
        </button>
      )}

      {expanded && template.section_headers.length > 0 && (
        <div className="mt-2 pt-2 border-t border-border">
          <div className="flex flex-wrap gap-1">
            {template.section_headers.map((h) => (
              <span
                key={h}
                className="text-[10px] text-text-muted bg-surface-alt px-1.5 py-0.5 rounded"
              >
                {h}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function BlankSlateCard({
  isSelected,
  onSelect,
}: {
  isSelected: boolean
  onSelect: () => void
}) {
  return (
    <div
      className={`
        border-2 border-dashed rounded-lg p-4 cursor-pointer transition-all
        ${isSelected
          ? 'border-accent bg-accent/5'
          : 'border-border hover:border-border-solid'
        }
      `}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect() } }}
    >
      <h3 className="text-sm font-semibold text-text mb-1">Start fresh</h3>
      <p className="text-xs text-text-muted">
        Let the AI build your strategy from your answers alone — no template framework.
      </p>
    </div>
  )
}

export function TemplateSelector({ onSelect, onBack, isApplying }: TemplateSelectorProps) {
  const { data: templates, isLoading } = useStrategyTemplates()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [isBlankSelected, setIsBlankSelected] = useState(false)

  const handleSelectTemplate = (id: string) => {
    setSelectedId(id)
    setIsBlankSelected(false)
  }

  const handleSelectBlank = () => {
    setSelectedId(null)
    setIsBlankSelected(true)
  }

  const handleConfirm = () => {
    if (isBlankSelected) {
      onSelect(null)
    } else if (selectedId) {
      onSelect(selectedId)
    }
  }

  const hasSelection = isBlankSelected || selectedId !== null

  return (
    <div className="w-full max-w-2xl mx-auto">
      <h2 className="text-lg font-semibold text-text mb-1">
        Choose a starting framework
      </h2>
      <p className="text-sm text-text-muted mb-5">
        Start from a proven GTM template or go blank. The AI will personalize it
        with your answers.
      </p>

      {isLoading ? (
        <div className="flex items-center gap-2 py-8 justify-center">
          <div className="w-4 h-4 border-2 border-border border-t-accent rounded-full animate-spin" />
          <span className="text-sm text-text-muted">Loading templates...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-5">
          {templates?.map((t) => (
            <TemplateCard
              key={t.id}
              template={t}
              isSelected={selectedId === t.id}
              onSelect={() => handleSelectTemplate(t.id)}
            />
          ))}
          <BlankSlateCard
            isSelected={isBlankSelected}
            onSelect={handleSelectBlank}
          />
        </div>
      )}

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onBack}
          disabled={isApplying}
          className="text-sm text-text-muted hover:text-text transition-colors bg-transparent border-none cursor-pointer p-0 disabled:opacity-40"
        >
          &larr; Back
        </button>

        <button
          onClick={handleConfirm}
          disabled={!hasSelection || isApplying}
          className="px-4 py-2 text-sm font-medium rounded-md bg-accent text-white hover:bg-accent-hover transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {isApplying ? 'Applying...' : 'Continue'}
        </button>
      </div>
    </div>
  )
}
