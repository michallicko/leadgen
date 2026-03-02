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
  /** Fired when proactive analysis starts streaming (after strategy edits). */
  onAnalysisStart?: () => void
  /** Fired for each text chunk of the proactive analysis. */
  onAnalysisChunk?: (text: string) => void
  /** Fired when proactive analysis completes with extracted suggestions. */
  onAnalysisDone?: (data: AnalysisDoneEventData) => void
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
 * Dispatch a parsed SSE event to the appropriate callback.
 */
function dispatchEvent(event: Record<string, unknown>, callbacks: UseSSECallbacks): void {
  const eventType = event.type as string | undefined

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
      output: event.output as Record<string, unknown> | undefined,
      durationMs: event.duration_ms as number,
    })
  } else if (eventType === 'thinking') {
    callbacks.onThinking?.((event.text as string) ?? '')
  } else if (eventType === 'analysis_start') {
    callbacks.onAnalysisStart?.()
  } else if (eventType === 'analysis_chunk') {
    callbacks.onAnalysisChunk?.(event.text as string)
  } else if (eventType === 'analysis_done') {
    callbacks.onAnalysisDone?.({
      messageId: event.message_id as string,
      suggestions: (event.suggestions as string[]) ?? [],
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
