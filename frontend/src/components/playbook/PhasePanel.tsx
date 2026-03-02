/**
 * PhasePanel -- left-panel component switcher based on active phase.
 *
 * Strategy phase renders the StrategyEditor (existing).
 * Contacts phase renders the ContactsPhasePanel with ICP pre-filters.
 * Messages phase renders the MessagesPhasePanel.
 * Other phases render placeholder stubs for now.
 */

import { StrategyEditor } from './StrategyEditor'
import { ContactsPhasePanel } from './ContactsPhasePanel'
import { MessagesPhasePanel } from './MessagesPhasePanel'

interface PhasePanelProps {
  phase: string
  content: string | null
  onEditorUpdate: (content: string) => void
  editable: boolean
  extractedData?: Record<string, unknown>
  playbookSelections?: Record<string, unknown>
  playbookId?: string
  selections?: Record<string, unknown>
  onPhaseAdvance?: (phase: string) => void
}

export function PhasePanel({
  phase,
  content,
  onEditorUpdate,
  editable,
  extractedData,
  playbookSelections,
  playbookId,
  selections,
  onPhaseAdvance,
}: PhasePanelProps) {
  switch (phase) {
    case 'strategy':
      return (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <StrategyEditor content={content} onUpdate={onEditorUpdate} editable={editable} />
        </div>
      )
    case 'contacts': {
      const existingSelections =
        (playbookSelections?.contacts as { selected_ids?: string[] })?.selected_ids ?? []
      return (
        <ContactsPhasePanel
          extractedData={extractedData ?? {}}
          existingSelections={existingSelections}
        />
      )
    }
    case 'messages':
      return (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <MessagesPhasePanel
            playbookId={playbookId}
            onPhaseAdvance={onPhaseAdvance}
          />
        </div>
      )
    case 'campaign':
      return <PhasePlaceholder title="Campaign Management" description="Configure sequencing, timing, and launch your outreach campaign." />
    default:
      return (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <StrategyEditor content={content} onUpdate={onEditorUpdate} editable={editable} />
        </div>
      )
  }
}

function PhasePlaceholder({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex-1 min-h-0 flex items-center justify-center">
      <div className="text-center max-w-md px-6">
        <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-5">
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-accent"
          >
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M12 8v8M8 12h8" />
          </svg>
        </div>
        <h2 className="text-lg font-semibold font-title text-text mb-2">{title}</h2>
        <p className="text-sm text-text-muted leading-relaxed">{description}</p>
        <p className="text-xs text-text-dim mt-4">
          Coming soon. Use the chat to discuss this phase with your AI strategist.
        </p>
      </div>
    </div>
  )
}
