/**
 * PhasePanel — left-panel component switcher based on active phase.
 *
 * Strategy phase renders the StrategyEditor (existing).
 * Other phases render placeholder stubs for now.
 */

import { StrategyEditor } from './StrategyEditor'

interface PhasePanelProps {
  phase: string
  content: string | null
  onEditorUpdate: (content: string) => void
  editable: boolean
}

export function PhasePanel({ phase, content, onEditorUpdate, editable }: PhasePanelProps) {
  switch (phase) {
    case 'strategy':
      return (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <StrategyEditor content={content} onUpdate={onEditorUpdate} editable={editable} />
        </div>
      )
    case 'contacts':
      return <PhasePlaceholder title="Contact Selection" description="Select target companies and contacts based on your ICP strategy. AI will help recommend the best matches." />
    case 'messages':
      return <PhasePlaceholder title="Message Generation" description="Craft personalized outreach messages for your selected contacts. AI will draft messages using your strategy and enrichment data." />
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
