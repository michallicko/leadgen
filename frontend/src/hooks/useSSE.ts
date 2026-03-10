/**
 * SSE streaming hook — consumes Server-Sent Events from POST requests.
 *
 * Uses fetch() + ReadableStream instead of EventSource (which only supports GET).
 * Parses SSE `data:` lines, handles partial chunks via TextDecoder buffering,
 * and supports cancellation via AbortController.
 */

import { useState, useRef, useCallback } from 'react'

/** Summary of a single tool call returned in the `done` event. */
export interface ToolCallSummary {
  tool_name: string
  status: 'success' | 'error'
}

/** Payload from a `tool_start` SSE event. */
export interface ToolStartEvent {
  toolCallId: string
  toolName: string
  input: Record<string, unknown>
}

/** Payload from a `tool_result` SSE event. */
export interface ToolResultEvent {
  toolCallId: string
  toolName?: string
  status: 'success' | 'error'
  summary: string
  output?: Record<string, unknown>
  durationMs: number
}

/** Payload from a `research_finding` SSE event. */
export interface ResearchFindingEvent {
  action: string
  finding: string
  step?: number
}

/** Quick action from the `done` event. */
export interface QuickActionEvent {
  label: string
  action: string
  type: 'chat_action' | 'navigate'
  target?: string
}

/** Payload from the enhanced `done` event. */
export interface DoneEventData {
  messageId: string
  toolCalls?: ToolCallSummary[]
  documentChanged?: boolean
  changesSummary?: string | null
  quickActions?: QuickActionEvent[]
}

/** Payload from the `analysis_done` event. */
export interface AnalysisDoneEventData {
  messageId: string
  suggestions: string[]
}

/** Payload from a `section_update` SSE event (live doc animation). */
export interface SectionUpdateEvent {
  section: string
  content: string
  action: 'update' | 'append'
}

/** Payload from a `research_status` SSE event. */
export interface ResearchStatusEvent {
  status: 'in_progress' | 'completed' | 'timeout'
  domain: string
  message: string
}

/** Payload from a halt gate request event. */
export interface HaltGateRequestEvent {
  gateId: string
  gateType: string
  question: string
  options: Array<{ label: string; value: string; description?: string }>
  context: string
  metadata: Record<string, unknown>
}

/** Payload from a generative UI component event. */
export interface GenerativeUIComponentEvent {
  componentType: string
  componentId: string
  props: Record<string, unknown>
  action: 'add' | 'update' | 'remove'
}

/** Payload from a document edit event. */
export interface DocumentEditSSEEvent {
  editId: string
  section: string
  operation: 'insert' | 'replace' | 'delete'
  content: string
  position: string
}

/** Payload from a state snapshot event. */
export interface StateSnapshotEvent {
  snapshot: Record<string, unknown>
}

/** Payload from a state delta event with JSON Patch operations. */
export interface StateDeltaEvent {
  delta: Record<string, unknown>
  operations?: Array<{ op: string; path: string; value?: unknown }>
}

export interface UseSSECallbacks {
  onChunk: (text: string) => void
  onDone: (data: DoneEventData) => void
  onError: (error: Error) => void
  /** Fired when the AI starts executing a tool. */
  onToolStart?: (event: ToolStartEvent) => void
  /** Fired when a tool execution completes (success or error). */
  onToolResult?: (result: ToolResultEvent) => void
  /** Fired when the AI emits a thinking/reasoning block (v2/optional). */
  onThinking?: (text: string) => void
  /** Fired when a strategy section is updated (live document animation). */
  onSectionUpdate?: (event: SectionUpdateEvent) => void
  /** Fired when proactive analysis starts streaming (after strategy edits). */
  onAnalysisStart?: () => void
  /** Fired for each text chunk of the proactive analysis. */
  onAnalysisChunk?: (text: string) => void
  /** Fired when proactive analysis completes with extracted suggestions. */
  onAnalysisDone?: (data: AnalysisDoneEventData) => void
  /** Fired when research status updates arrive (before AI generation). */
  onResearchStatus?: (event: ResearchStatusEvent) => void
  /** Fired when section content streaming starts (typewriter effect). */
  onSectionContentStart?: (section: string) => void
  /** Fired for each text chunk of section content streaming. */
  onSectionContentChunk?: (text: string) => void
  /** Fired when section content streaming completes. */
  onSectionContentDone?: (section: string) => void
  /** Fired when a halt gate request arrives (agent paused for user decision). */
  onHaltGateRequest?: (event: HaltGateRequestEvent) => void
  /** Fired when a generative UI component event arrives. */
  onGenerativeUI?: (event: GenerativeUIComponentEvent) => void
  /** Fired when a document edit event arrives. */
  onDocumentEdit?: (event: DocumentEditSSEEvent) => void
  /** Fired when a full state snapshot arrives (connection/reconnect). */
  onStateSnapshot?: (event: StateSnapshotEvent) => void
  /** Fired when a state delta with JSON Patch operations arrives. */
  onStateDelta?: (event: StateDeltaEvent) => void
  /** Fired when the agent emits a research finding (BL-1015). */
  onResearchFinding?: (event: ResearchFindingEvent) => void
}

interface UseSSEReturn {
  isStreaming: boolean
  startStream: (
    url: string,
    body: object,
    headers: Record<string, string>,
    callbacks: UseSSECallbacks,
  ) => Promise<void>
  abort: () => void
}

/**
 * Parse a single SSE event block (text between double newlines).
 * Returns the parsed JSON data payload, or null if the block is empty / unparseable.
 */
function parseSSEEvent(block: string): Record<string, unknown> | null {
  const lines = block.split('\n')
  let data = ''

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      data += line.slice(6)
    } else if (line.startsWith('data:')) {
      data += line.slice(5)
    }
    // Ignore comment lines (starting with :) and other fields (event:, id:, retry:)
  }

  if (!data) return null

  try {
    return JSON.parse(data) as Record<string, unknown>
  } catch {
    return null
  }
}

/**
 * Parse output from a tool_result or TOOL_CALL_END event.
 * The backend sends output as a JSON-encoded string — parse it so
 * ToolCallCard receives a proper object for rendering.
 */
function parseToolOutput(raw: unknown): Record<string, unknown> | undefined {
  if (typeof raw === 'string' && raw) {
    try {
      const parsed = JSON.parse(raw)
      if (typeof parsed === 'object' && parsed !== null) {
        return parsed as Record<string, unknown>
      }
    } catch {
      // Not valid JSON — leave as undefined
    }
  } else if (typeof raw === 'object' && raw !== null) {
    return raw as Record<string, unknown>
  }
  return undefined
}

/**
 * Dispatch a parsed SSE event to the appropriate callback.
 *
 * Supports both legacy custom events (chunk, tool_start, tool_result, done)
 * and AG-UI protocol events (TEXT_MESSAGE_CONTENT, TOOL_CALL_START, etc.).
 * This enables gradual migration from custom to AG-UI events.
 */
function dispatchEvent(event: Record<string, unknown>, callbacks: UseSSECallbacks): void {
  const eventType = event.type as string | undefined

  // --- Legacy custom events ---
  if (eventType === 'chunk') {
    callbacks.onChunk(event.text as string)
  } else if (eventType === 'done') {
    callbacks.onDone({
      messageId: event.message_id as string,
      toolCalls: event.tool_calls as ToolCallSummary[] | undefined,
      documentChanged: event.document_changed as boolean | undefined,
      changesSummary: event.changes_summary as string | null | undefined,
      quickActions: event.quick_actions as QuickActionEvent[] | undefined,
    })
  } else if (eventType === 'error') {
    callbacks.onError(new Error((event.message as string) ?? 'Stream error'))
  } else if (eventType === 'tool_start') {
    callbacks.onToolStart?.({
      toolCallId: event.tool_call_id as string,
      toolName: event.tool_name as string,
      input: (event.input as Record<string, unknown>) ?? {},
    })
  } else if (eventType === 'tool_result') {
    callbacks.onToolResult?.({
      toolCallId: event.tool_call_id as string,
      toolName: event.tool_name as string | undefined,
      status: event.status as 'success' | 'error',
      summary: event.summary as string,
      output: parseToolOutput(event.output),
      durationMs: event.duration_ms as number,
    })
  } else if (eventType === 'thinking') {
    callbacks.onThinking?.((event.text as string) ?? '')
  } else if (eventType === 'section_update') {
    callbacks.onSectionUpdate?.({
      section: event.section as string,
      content: event.content as string,
      action: event.action as 'update' | 'append',
    })
  } else if (eventType === 'analysis_start') {
    callbacks.onAnalysisStart?.()
  } else if (eventType === 'analysis_chunk') {
    callbacks.onAnalysisChunk?.(event.text as string)
  } else if (eventType === 'analysis_done') {
    callbacks.onAnalysisDone?.({
      messageId: event.message_id as string,
      suggestions: (event.suggestions as string[]) ?? [],
    })
  } else if (eventType === 'research_status') {
    callbacks.onResearchStatus?.({
      status: event.status as ResearchStatusEvent['status'],
      domain: event.domain as string,
      message: event.message as string,
    })
  } else if (eventType === 'section_content_start') {
    callbacks.onSectionContentStart?.(event.section as string)
  } else if (eventType === 'section_content_chunk') {
    callbacks.onSectionContentChunk?.(event.text as string)
  } else if (eventType === 'section_content_done') {
    callbacks.onSectionContentDone?.(event.section as string)
  } else if (eventType === 'research_finding') {
    callbacks.onResearchFinding?.({
      action: event.action as string,
      finding: event.finding as string,
      step: event.step as number | undefined,
    })

  // --- AG-UI protocol events ---
  } else if (eventType === 'RUN_STARTED') {
    // No-op for now — future: could set a "run in progress" state
  } else if (eventType === 'RUN_FINISHED') {
    // Map to onDone with AG-UI field names
    callbacks.onDone({
      messageId: (event.runId as string) ?? '',
      toolCalls: event.tool_calls as ToolCallSummary[] | undefined,
      documentChanged: event.document_changed as boolean | undefined,
      changesSummary: event.changes_summary as string | null | undefined,
    })
  } else if (eventType === 'TEXT_MESSAGE_START') {
    // If section is present, this is a section content stream
    if (event.section) {
      callbacks.onSectionContentStart?.(event.section as string)
    }
    // Otherwise, start of regular text — no-op (chunk handles content)
  } else if (eventType === 'TEXT_MESSAGE_CONTENT') {
    const delta = (event.delta as string) ?? ''
    const msgId = (event.messageId as string) ?? ''
    // Route section content to section callbacks
    if (msgId.endsWith('_section')) {
      callbacks.onSectionContentChunk?.(delta)
    } else {
      callbacks.onChunk(delta)
    }
  } else if (eventType === 'TEXT_MESSAGE_END') {
    if (event.section) {
      callbacks.onSectionContentDone?.(event.section as string)
    }
  } else if (eventType === 'TOOL_CALL_START') {
    callbacks.onToolStart?.({
      toolCallId: (event.toolCallId as string) ?? '',
      toolName: (event.toolCallName as string) ?? '',
      input: (event.input as Record<string, unknown>) ?? {},
    })
  } else if (eventType === 'TOOL_CALL_END') {
    callbacks.onToolResult?.({
      toolCallId: (event.toolCallId as string) ?? '',
      toolName: (event.toolCallName as string) ?? undefined,
      status: (event.status as 'success' | 'error') ?? 'success',
      summary: (event.summary as string) ?? '',
      output: parseToolOutput(event.output),
      durationMs: (event.durationMs as number) ?? 0,
    })
  } else if (eventType === 'STATE_DELTA') {
    // Map state delta to section_update if it contains section data
    const delta = event.delta as Record<string, unknown> | undefined
    if (delta?.section) {
      callbacks.onSectionUpdate?.({
        section: delta.section as string,
        content: (delta.content as string) ?? '',
        action: (delta.action as 'update' | 'append') ?? 'update',
      })
    }
    // Also emit the raw state delta for shared state sync
    const operations = event.operations as Array<{ op: string; path: string; value?: unknown }> | undefined
    if (operations || delta) {
      callbacks.onStateDelta?.({
        delta: delta ?? {},
        operations,
      })
    }
  } else if (eventType === 'STATE_SNAPSHOT') {
    const snapshot = event.snapshot as Record<string, unknown> | undefined
    if (snapshot) {
      callbacks.onStateSnapshot?.({ snapshot })
    }

  // --- Custom extension events ---
  } else if (eventType === 'CUSTOM:halt_gate_request') {
    callbacks.onHaltGateRequest?.({
      gateId: (event.gateId as string) ?? '',
      gateType: (event.gateType as string) ?? '',
      question: (event.question as string) ?? '',
      options: (event.options as HaltGateRequestEvent['options']) ?? [],
      context: (event.context as string) ?? '',
      metadata: (event.metadata as Record<string, unknown>) ?? {},
    })
  } else if (eventType === 'CUSTOM:generative_ui') {
    callbacks.onGenerativeUI?.({
      componentType: (event.componentType as string) ?? '',
      componentId: (event.componentId as string) ?? '',
      props: (event.props as Record<string, unknown>) ?? {},
      action: (event.action as 'add' | 'update' | 'remove') ?? 'add',
    })
  } else if (eventType === 'CUSTOM:document_edit') {
    callbacks.onDocumentEdit?.({
      editId: (event.editId as string) ?? '',
      section: (event.section as string) ?? '',
      operation: (event.operation as 'insert' | 'replace' | 'delete') ?? 'insert',
      content: (event.content as string) ?? '',
      position: (event.position as string) ?? 'end',
    })
  } else if (eventType === 'CUSTOM:research_status') {
    callbacks.onResearchStatus?.({
      status: event.status as ResearchStatusEvent['status'],
      domain: event.domain as string,
      message: event.message as string,
    })
  }
}

export function useSSE(): UseSSEReturn {
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const abort = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    setIsStreaming(false)
  }, [])

  const startStream = useCallback(
    async (
      url: string,
      body: object,
      headers: Record<string, string>,
      callbacks: UseSSECallbacks,
    ) => {
      // Cancel any in-flight stream
      if (abortRef.current) {
        abortRef.current.abort()
      }

      const controller = new AbortController()
      abortRef.current = controller
      setIsStreaming(true)

      try {
        const resp = await fetch(url, {
          method: 'POST',
          headers: {
            ...headers,
            Accept: 'text/event-stream',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
          signal: controller.signal,
        })

        if (!resp.ok) {
          let message = `Stream request failed (${resp.status})`
          try {
            const errBody = (await resp.json()) as { error?: string }
            if (errBody.error) message = errBody.error
          } catch {
            // non-JSON error body
          }
          throw new Error(message)
        }

        if (!resp.body) {
          throw new Error('Response body is not a readable stream')
        }

        const reader = resp.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()

          if (done) break

          buffer += decoder.decode(value, { stream: true })

          // SSE events are delimited by double newlines
          const parts = buffer.split('\n\n')

          // The last element may be an incomplete event — keep it in the buffer
          buffer = parts.pop() ?? ''

          for (const part of parts) {
            const trimmed = part.trim()
            if (!trimmed) continue

            const event = parseSSEEvent(trimmed)
            if (!event) continue

            dispatchEvent(event, callbacks)
          }
        }

        // Process any remaining buffer content
        if (buffer.trim()) {
          const event = parseSSEEvent(buffer.trim())
          if (event) {
            dispatchEvent(event, callbacks)
          }
        }
      } catch (err: unknown) {
        // AbortError is expected when user cancels — don't report it
        if (err instanceof DOMException && err.name === 'AbortError') {
          return
        }
        callbacks.onError(err instanceof Error ? err : new Error(String(err)))
      } finally {
        setIsStreaming(false)
        if (abortRef.current === controller) {
          abortRef.current = null
        }
      }
    },
    [],
  )

  return { isStreaming, startStream, abort }
}
