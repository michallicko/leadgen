/**
 * HaltGateUI — renders inline approval UI when the agent pauses at a decision point.
 *
 * Displays the gate question, context, and option buttons. For resource gates,
 * shows the estimated token cost. Supports an optional custom input field.
 */

import { useState } from 'react'
import type { HaltGateRequest } from '../../types/agui'

interface HaltGateUIProps {
  gate: HaltGateRequest
  onRespond: (choice: string, customInput?: string) => void
  isResponding: boolean
}

/** Badge styling per gate type. */
const GATE_TYPE_STYLES: Record<string, { label: string; className: string }> = {
  scope: { label: 'Scope', className: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300' },
  direction: { label: 'Direction', className: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300' },
  assumption: { label: 'Assumption', className: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300' },
  review: { label: 'Review', className: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300' },
  resource: { label: 'Cost Approval', className: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300' },
}

export function HaltGateUI({ gate, onRespond, isResponding }: HaltGateUIProps) {
  const [customInput, setCustomInput] = useState('')
  const [showCustomInput, setShowCustomInput] = useState(false)

  const typeStyle = GATE_TYPE_STYLES[gate.gateType] ?? {
    label: gate.gateType,
    className: 'bg-gray-100 text-gray-800',
  }

  const hasTokenEstimate = gate.gateType === 'resource' && gate.metadata?.estimatedTokens

  return (
    <div className="rounded-lg border border-accent/30 bg-accent/5 p-4 my-2 space-y-3">
      {/* Header: gate type badge */}
      <div className="flex items-center gap-2">
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${typeStyle.className}`}>
          {typeStyle.label}
        </span>
        {hasTokenEstimate && (
          <span className="text-xs font-mono text-text-muted bg-surface-alt px-2 py-0.5 rounded">
            ~{gate.metadata.estimatedTokens?.toLocaleString()} tokens
            {gate.metadata.estimatedCostUsd && ` ($${gate.metadata.estimatedCostUsd})`}
          </span>
        )}
      </div>

      {/* Context */}
      <p className="text-sm text-text-muted leading-relaxed">
        {gate.context}
      </p>

      {/* Question */}
      <p className="text-sm font-medium text-text">
        {gate.question}
      </p>

      {/* Option buttons */}
      <div className="flex flex-wrap gap-2">
        {gate.options.map((option) => (
          <button
            key={option.value}
            type="button"
            disabled={isResponding}
            onClick={() => onRespond(option.value)}
            className="px-3 py-1.5 text-sm font-medium rounded-md border border-border-solid
                       bg-surface hover:bg-surface-alt hover:border-accent/50
                       text-text transition-colors
                       disabled:opacity-50 disabled:cursor-not-allowed"
            title={option.description || undefined}
          >
            {option.label}
          </button>
        ))}

        {/* "Other" button to show custom input */}
        {!showCustomInput && (
          <button
            type="button"
            disabled={isResponding}
            onClick={() => setShowCustomInput(true)}
            className="px-3 py-1.5 text-sm rounded-md border border-dashed border-border-solid
                       text-text-muted hover:text-text hover:border-accent/50
                       transition-colors
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Other...
          </button>
        )}
      </div>

      {/* Custom input field */}
      {showCustomInput && (
        <div className="flex gap-2">
          <input
            type="text"
            value={customInput}
            onChange={(e) => setCustomInput(e.target.value)}
            placeholder="Type your choice..."
            className="flex-1 px-3 py-1.5 text-sm rounded-md border border-border-solid
                       bg-surface text-text placeholder:text-text-muted
                       focus:outline-none focus:ring-1 focus:ring-accent/50"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && customInput.trim()) {
                onRespond('custom', customInput.trim())
              }
            }}
            disabled={isResponding}
          />
          <button
            type="button"
            disabled={isResponding || !customInput.trim()}
            onClick={() => onRespond('custom', customInput.trim())}
            className="px-3 py-1.5 text-sm font-medium rounded-md
                       bg-accent text-white hover:bg-accent-hover
                       transition-colors
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>
      )}

      {/* Responding indicator */}
      {isResponding && (
        <p className="text-xs text-text-muted animate-pulse">
          Resuming agent with your choice...
        </p>
      )}
    </div>
  )
}
