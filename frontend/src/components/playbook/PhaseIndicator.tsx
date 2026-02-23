/**
 * PhaseIndicator — horizontal stepper showing the 4 playbook phases.
 *
 * States: completed (checkmark), active (highlighted), available (clickable), locked (grayed).
 * Clicking an unlocked phase fires onNavigate.
 */

import { Fragment } from 'react'

const PHASES = [
  { key: 'strategy', label: 'Strategy', icon: '1' },
  { key: 'contacts', label: 'Contacts', icon: '2' },
  { key: 'messages', label: 'Messages', icon: '3' },
  { key: 'campaign', label: 'Campaign', icon: '4' },
] as const

export type PhaseKey = (typeof PHASES)[number]['key']

export const PHASE_ORDER: PhaseKey[] = PHASES.map((p) => p.key)

interface PhaseIndicatorProps {
  /** Currently viewed phase (from URL) */
  current: string
  /** Highest unlocked phase (from DB) */
  unlocked: string
  /** Navigate to a phase */
  onNavigate: (phase: string) => void
}

export function PhaseIndicator({ current, unlocked, onNavigate }: PhaseIndicatorProps) {
  const unlockedIdx = PHASES.findIndex((p) => p.key === unlocked)

  return (
    <div className="flex items-center gap-0 mb-3 px-2">
      {PHASES.map((phase, idx) => {
        const isUnlocked = idx <= unlockedIdx
        const isCurrent = phase.key === current
        const isCompleted = idx < unlockedIdx

        return (
          <Fragment key={phase.key}>
            {/* Connector line between phases */}
            {idx > 0 && (
              <div
                className={`flex-1 h-px mx-2 ${
                  isCompleted ? 'bg-success' : 'bg-border-solid'
                }`}
              />
            )}

            {/* Phase button */}
            <button
              onClick={() => isUnlocked && onNavigate(phase.key)}
              disabled={!isUnlocked}
              title={!isUnlocked ? 'Complete the previous phase to unlock' : undefined}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs
                font-medium transition-colors cursor-pointer
                ${
                  isCurrent
                    ? 'bg-accent/15 text-accent border border-accent/30'
                    : isCompleted
                      ? 'text-success hover:bg-success/10 border border-transparent'
                      : isUnlocked
                        ? 'text-text-muted hover:bg-surface-alt border border-transparent'
                        : 'text-text-dim opacity-50 cursor-not-allowed border border-transparent'
                }`}
            >
              <span
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                  isCompleted
                    ? 'bg-success text-white'
                    : isCurrent
                      ? 'bg-accent text-white'
                      : 'bg-surface-alt text-text-dim'
                }`}
              >
                {isCompleted ? '\u2713' : phase.icon}
              </span>
              {phase.label}
            </button>
          </Fragment>
        )
      })}
    </div>
  )
}
