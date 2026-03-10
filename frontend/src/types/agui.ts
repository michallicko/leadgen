/**
 * AG-UI protocol TypeScript types.
 *
 * Defines types for all AG-UI events consumed by the frontend,
 * including standard events and custom extensions for halt gates,
 * generative UI, document editing, and shared state.
 */

// ---------------------------------------------------------------------------
// AG-UI Event Types (constants)
// ---------------------------------------------------------------------------

export const AG_UI_EVENTS = {
  RUN_STARTED: 'RUN_STARTED',
  RUN_FINISHED: 'RUN_FINISHED',
  TEXT_MESSAGE_START: 'TEXT_MESSAGE_START',
  TEXT_MESSAGE_CONTENT: 'TEXT_MESSAGE_CONTENT',
  TEXT_MESSAGE_END: 'TEXT_MESSAGE_END',
  TOOL_CALL_START: 'TOOL_CALL_START',
  TOOL_CALL_ARGS: 'TOOL_CALL_ARGS',
  TOOL_CALL_END: 'TOOL_CALL_END',
  STATE_DELTA: 'STATE_DELTA',
  STATE_SNAPSHOT: 'STATE_SNAPSHOT',
  // Custom extensions
  HALT_GATE_REQUEST: 'CUSTOM:halt_gate_request',
  HALT_GATE_RESPONSE: 'CUSTOM:halt_gate_response',
  DOCUMENT_EDIT: 'CUSTOM:document_edit',
  GENERATIVE_UI: 'CUSTOM:generative_ui',
  RESEARCH_STATUS: 'CUSTOM:research_status',
  THINKING_STATUS: 'CUSTOM:thinking_status',
} as const

// ---------------------------------------------------------------------------
// Halt Gate Types
// ---------------------------------------------------------------------------

export type HaltGateType = 'scope' | 'direction' | 'assumption' | 'review' | 'resource'

export type HaltFrequency = 'always' | 'major_only' | 'autonomous'

export interface HaltGateOption {
  label: string
  value: string
  description?: string
}

export interface HaltGateRequest {
  gateId: string
  gateType: HaltGateType
  question: string
  options: HaltGateOption[]
  context: string
  metadata: {
    estimatedTokens?: number
    estimatedCostUsd?: string
    [key: string]: unknown
  }
}

export interface HaltGateResponsePayload {
  threadId: string
  runId: string
  gateId: string
  choice: string
  customInput?: string | null
}

// ---------------------------------------------------------------------------
// Generative UI Types
// ---------------------------------------------------------------------------

export type GenerativeUIComponentType =
  | 'data_table'
  | 'progress_card'
  | 'comparison_view'
  | 'approval_buttons'

export type GenerativeUIAction = 'add' | 'update' | 'remove'

export interface GenerativeUIEvent {
  componentType: GenerativeUIComponentType
  componentId: string
  props: Record<string, unknown>
  action: GenerativeUIAction
}

/** Props for the data_table generative UI component. */
export interface DataTableProps {
  title?: string
  columns: Array<{ key: string; label: string; sortable?: boolean }>
  rows: Array<Record<string, unknown>>
}

/** Props for the progress_card generative UI component. */
export interface ProgressCardProps {
  title: string
  progress: number // 0-100
  status: string
  details?: string
}

/** Props for the comparison_view generative UI component. */
export interface ComparisonViewProps {
  title?: string
  items: Array<{
    label: string
    description: string
    pros?: string[]
    cons?: string[]
  }>
}

// ---------------------------------------------------------------------------
// Shared State Types
// ---------------------------------------------------------------------------

export interface AgentSharedState {
  currentPhase: string
  activeSection: string | null
  docCompleteness: Record<string, number>
  enrichmentStatus: string
  contextSummary: string
  haltGatesPending: string[]
  components: GenerativeUIComponentState[]
}

export interface GenerativeUIComponentState {
  id: string
  type: GenerativeUIComponentType
  props: Record<string, unknown>
}

/** RFC 6902 JSON Patch operation. */
export interface JsonPatchOperation {
  op: 'add' | 'replace' | 'remove'
  path: string
  value?: unknown
}

// ---------------------------------------------------------------------------
// Document Edit Types
// ---------------------------------------------------------------------------

export type DocumentEditOperation = 'insert' | 'replace' | 'delete'

export interface DocumentEditEvent {
  editId: string
  section: string
  operation: DocumentEditOperation
  content: string
  position: string // 'start', 'end', or character offset
}

// ---------------------------------------------------------------------------
// Suggestion Types (for accept/reject changes)
// ---------------------------------------------------------------------------

export type SuggestionType = 'add' | 'delete' | 'replace'

export interface Suggestion {
  id: string
  type: SuggestionType
  section: string
  content: string
  originalContent?: string
  /** Position in the document (Tiptap position). */
  from: number
  to: number
}
