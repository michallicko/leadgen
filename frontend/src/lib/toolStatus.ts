/**
 * Maps internal tool names to user-friendly status messages for the
 * thinking/progress indicator in the chat UI.
 */

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
