/**
 * ThinkingIndicator -- animated pulsing dot + dynamic status text shown
 * while the AI is processing.
 *
 * Appears inline in the message stream (same layout as StreamingBubble)
 * after the user sends a message. Shows a single pulsing dot with a
 * one-liner status message describing what the AI is doing (e.g.,
 * "Researching your market...", "Updating strategy...").
 *
 * Disappears when the streaming text (final response) starts appearing.
 */

// ---------------------------------------------------------------------------
// Icons (duplicated from ChatMessages to keep this self-contained)
// ---------------------------------------------------------------------------

function AssistantIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="2" y="3" width="12" height="10" rx="2" />
      <circle cx="6" cy="8" r="1" fill="currentColor" stroke="none" />
      <circle cx="10" cy="8" r="1" fill="currentColor" stroke="none" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Tool name → user-friendly status mapping
// ---------------------------------------------------------------------------

const TOOL_STATUS_MAP: Record<string, string> = {
  // Strategy tools
  get_strategy_document: 'Reading strategy...',
  update_strategy_section: 'Updating strategy...',
  set_extracted_field: 'Extracting insights...',
  append_to_section: 'Updating strategy...',
  track_assumption: 'Tracking assumptions...',
  check_readiness: 'Checking readiness...',
  set_icp_tiers: 'Defining customer tiers...',
  set_buyer_personas: 'Defining buyer personas...',

  // Search tools
  web_search: 'Researching your market...',

  // Analyze tools
  count_contacts: 'Analyzing contacts...',
  count_companies: 'Analyzing companies...',
  list_contacts: 'Looking up contacts...',
  list_companies: 'Looking up companies...',

  // Campaign tools
  filter_contacts: 'Filtering contacts...',
  create_campaign: 'Creating campaign...',
  assign_to_campaign: 'Assigning contacts...',
  check_strategy_conflicts: 'Checking for conflicts...',
  get_campaign_summary: 'Reviewing campaign...',

  // Enrichment tools
  analyze_enrichment_insights: 'Analyzing enrichment data...',
  get_enrichment_gaps: 'Checking data coverage...',
}

/** Convert a tool_name to a user-friendly status message. */
export function getToolStatusText(toolName: string | null): string {
  if (!toolName) return 'Thinking...'
  return TOOL_STATUS_MAP[toolName] ?? `Running ${toolName.replace(/_/g, ' ')}...`
}

// ---------------------------------------------------------------------------
// ThinkingIndicator
// ---------------------------------------------------------------------------

interface ThinkingIndicatorProps {
  /** Dynamic status text to display (e.g., "Researching your market...") */
  statusText?: string
}

export function ThinkingIndicator({ statusText = 'Thinking...' }: ThinkingIndicatorProps) {
  return (
    <div className="flex gap-3 flex-row">
      {/* Avatar -- same as assistant messages */}
      <div className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5 bg-accent-cyan/15 text-accent-cyan">
        <AssistantIcon />
      </div>

      {/* Pulsing dot + status text */}
      <div className="rounded-lg px-4 py-2.5 bg-surface-alt border border-border-solid flex items-center gap-2.5">
        <span
          className="w-2 h-2 rounded-full bg-accent-cyan flex-shrink-0"
          style={{ animation: 'thinkPulse 1.4s ease-in-out infinite' }}
        />
        <span className="text-xs text-text-muted truncate max-w-[240px]">
          {statusText}
        </span>
      </div>
    </div>
  )
}
