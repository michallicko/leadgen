/**
 * AG-UI Protocol event dispatcher — maps AG-UI events to legacy SSE callbacks.
 *
 * This module provides a dispatcher function that handles AG-UI protocol events
 * (RUN_STARTED, TEXT_MESSAGE_CONTENT, TOOL_CALL_START, etc.) and maps them to
 * the same UseSSECallbacks interface used by the legacy SSE protocol.
 *
 * To integrate with useSSE.ts, the dispatchEvent function should call
 * dispatchAGUIEvent for any event type it doesn't recognize (i.e., AG-UI events
 * that start with uppercase like 'TEXT_MESSAGE_CONTENT').
 *
 * BL-252: AG-UI Protocol Adoption
 */

import type {
  UseSSECallbacks,
  ToolCallSummary,
} from './useSSE'

// ---------------------------------------------------------------------------
// AG-UI stream state — tracks accumulated state from STATE_DELTA events
// ---------------------------------------------------------------------------

export interface AGUIStreamState {
  documentChanged: boolean
  changesSummary: string | null
}

export function createAGUIStreamState(): AGUIStreamState {
  return { documentChanged: false, changesSummary: null }
}

// ---------------------------------------------------------------------------
// AG-UI event type constants
// ---------------------------------------------------------------------------

export const AGUI_EVENT_TYPES = {
  RUN_STARTED: 'RUN_STARTED',
  RUN_FINISHED: 'RUN_FINISHED',
  TEXT_MESSAGE_START: 'TEXT_MESSAGE_START',
  TEXT_MESSAGE_CONTENT: 'TEXT_MESSAGE_CONTENT',
  TEXT_MESSAGE_END: 'TEXT_MESSAGE_END',
  TOOL_CALL_START: 'TOOL_CALL_START',
  TOOL_CALL_ARGS: 'TOOL_CALL_ARGS',
  TOOL_CALL_END: 'TOOL_CALL_END',
  STATE_DELTA: 'STATE_DELTA',
} as const

/**
 * Check if an event type string is an AG-UI protocol event.
 * AG-UI events use UPPER_SNAKE_CASE, legacy events use lowercase.
 */
export function isAGUIEvent(eventType: string | undefined): boolean {
  if (!eventType) return false
  return eventType === eventType.toUpperCase() && eventType.includes('_')
}

// ---------------------------------------------------------------------------
// AG-UI event dispatcher
// ---------------------------------------------------------------------------

/**
 * Dispatch an AG-UI protocol event to the appropriate UseSSECallbacks handler.
 *
 * Maps AG-UI events to the legacy callback interface:
 *   TEXT_MESSAGE_CONTENT → onChunk(delta)
 *   TOOL_CALL_START → onToolStart({toolCallId, toolName, input: {}})
 *   TOOL_CALL_END → onToolResult({toolCallId, toolName, status, summary, durationMs})
 *   STATE_DELTA → updates aguiState (document_changed, changes_summary)
 *   RUN_FINISHED → onDone({messageId, toolCalls, documentChanged, changesSummary})
 *
 * Events with no direct mapping (RUN_STARTED, TEXT_MESSAGE_START,
 * TEXT_MESSAGE_END, TOOL_CALL_ARGS) are silently handled.
 *
 * @param event - Parsed SSE event payload
 * @param callbacks - UseSSECallbacks from the streaming hook
 * @param aguiState - Mutable state object for tracking STATE_DELTA changes
 * @returns true if the event was handled, false if not recognized
 */
export function dispatchAGUIEvent(
  event: Record<string, unknown>,
  callbacks: UseSSECallbacks,
  aguiState: AGUIStreamState,
): boolean {
  const eventType = event.type as string | undefined

  switch (eventType) {
    case AGUI_EVENT_TYPES.RUN_STARTED:
      // No direct callback — run lifecycle is implicit in the stream
      return true

    case AGUI_EVENT_TYPES.TEXT_MESSAGE_START:
      // No direct callback — text start is implicit
      return true

    case AGUI_EVENT_TYPES.TEXT_MESSAGE_CONTENT:
      // Map to onChunk (same as legacy 'chunk')
      callbacks.onChunk((event.delta as string) ?? '')
      return true

    case AGUI_EVENT_TYPES.TEXT_MESSAGE_END:
      // No direct callback — text end is signaled by RUN_FINISHED
      return true

    case AGUI_EVENT_TYPES.TOOL_CALL_START:
      callbacks.onToolStart?.({
        toolCallId: event.tool_call_id as string,
        toolName: event.tool_name as string,
        input: {}, // Input comes via TOOL_CALL_ARGS
      })
      return true

    case AGUI_EVENT_TYPES.TOOL_CALL_ARGS:
      // Tool args are streamed incrementally. We don't currently surface
      // partial args to the UI — they could be accumulated here if needed.
      return true

    case AGUI_EVENT_TYPES.TOOL_CALL_END:
      callbacks.onToolResult?.({
        toolCallId: event.tool_call_id as string,
        toolName: event.tool_name as string | undefined,
        status: event.status as 'success' | 'error',
        summary: (event.summary as string) ?? '',
        durationMs: (event.duration_ms as number) ?? 0,
      })
      return true

    case AGUI_EVENT_TYPES.STATE_DELTA: {
      // Process JSON Patch operations to track shared state changes
      const delta = event.delta as
        | Array<{ op: string; path: string; value: unknown }>
        | undefined
      if (delta) {
        for (const op of delta) {
          if (op.path === '/document_changed') {
            aguiState.documentChanged = op.value as boolean
          } else if (op.path === '/changes_summary') {
            aguiState.changesSummary = op.value as string | null
          }
        }
      }
      return true
    }

    case AGUI_EVENT_TYPES.RUN_FINISHED: {
      // Map to onDone — synthesize DoneEventData from AG-UI fields
      const toolCalls = event.tool_calls as ToolCallSummary[] | undefined
      callbacks.onDone({
        messageId: (event.run_id as string) ?? '',
        toolCalls,
        documentChanged: aguiState.documentChanged || undefined,
        changesSummary: aguiState.changesSummary,
      })
      return true
    }

    default:
      return false
  }
}
