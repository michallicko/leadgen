/**
 * SSE streaming hook — consumes Server-Sent Events from POST requests.
 *
 * Uses fetch() + ReadableStream instead of EventSource (which only supports GET).
 * Parses SSE `data:` lines, handles partial chunks via TextDecoder buffering,
 * and supports cancellation via AbortController.
 */

import { useState, useRef, useCallback } from 'react'

export interface UseSSECallbacks {
  onChunk: (text: string) => void
  onDone: (messageId: string) => void
  onError: (error: Error) => void
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

            const eventType = event.type as string | undefined

            if (eventType === 'chunk') {
              callbacks.onChunk(event.text as string)
            } else if (eventType === 'done') {
              callbacks.onDone(event.message_id as string)
            } else if (eventType === 'error') {
              callbacks.onError(new Error((event.error as string) ?? 'Stream error'))
            }
          }
        }

        // Process any remaining buffer content
        if (buffer.trim()) {
          const event = parseSSEEvent(buffer.trim())
          if (event) {
            const eventType = event.type as string | undefined
            if (eventType === 'chunk') {
              callbacks.onChunk(event.text as string)
            } else if (eventType === 'done') {
              callbacks.onDone(event.message_id as string)
            } else if (eventType === 'error') {
              callbacks.onError(new Error((event.error as string) ?? 'Stream error'))
            }
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
