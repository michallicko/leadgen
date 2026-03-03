/**
 * WorkflowProgressStrip — persistent mini workflow bar above chat input.
 *
 * Shows the user's GTM progress: Strategy > Contacts > Enrich > Messages > Campaign
 * with cyan-accented dots and milestone labels.
 *
 * BL-135: Proactive Next-Step Suggestions — progress strip component.
 */

import { useWorkflowStatus, PHASES, type WorkflowPhase } from '../../hooks/useWorkflowStatus'

const PHASE_LABELS: Record<WorkflowPhase, string> = {
  strategy: 'Strategy',
  contacts: 'Contacts',
  enrich: 'Enrich',
  messages: 'Messages',
  campaign: 'Campaign',
}

export function WorkflowProgressStrip() {
  const { data: status, isLoading } = useWorkflowStatus()

  if (isLoading || !status) return null

  return (
    <div className="flex items-center gap-1.5 px-4 py-2 border-t border-border-solid bg-surface flex-shrink-0">
      {PHASES.map((phase, i) => {
        const isCompleted = status.completedPhases.includes(phase)
        const isCurrent = status.currentPhase === phase

        return (
          <div key={phase} className="flex items-center gap-1.5">
            {i > 0 && (
              <div
                className={`w-4 h-px ${
                  isCompleted ? 'bg-accent-cyan' : 'bg-border-solid'
                }`}
              />
            )}
            <div className="flex items-center gap-1">
              <div
                className={`w-2 h-2 rounded-full transition-colors ${
                  isCompleted
                    ? 'bg-accent-cyan'
                    : isCurrent
                      ? 'bg-accent-cyan animate-pulse'
                      : 'bg-border-solid'
                }`}
              />
              <span
                className={`text-[10px] font-medium whitespace-nowrap ${
                  isCompleted
                    ? 'text-accent-cyan'
                    : isCurrent
                      ? 'text-text'
                      : 'text-text-dim'
                }`}
              >
                {PHASE_LABELS[phase]}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
