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

/** Payload from the enhanced `done` event. */
export interface DoneEventData {
  messageId: string
  toolCalls?: ToolCallSummary[]
  documentChanged?: boolean
  changesSummary?: string | null
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
