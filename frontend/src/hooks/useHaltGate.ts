/**
 * useHaltGate — manages halt gate state and user responses.
 *
 * When the agent pauses at a decision point, this hook stores the
 * pending gate and provides a function to send the user's choice
 * back to the backend to resume execution.
 */

import { useState, useCallback } from 'react'
import type { HaltGateRequest, HaltGateResponsePayload } from '../types/agui'
import { resolveApiBase, buildHeaders } from '../api/client'
import { getAccessToken } from '../lib/auth'

interface UseHaltGateReturn {
  /** The currently pending halt gate, or null if none. */
  pendingGate: HaltGateRequest | null
  /** Set a new pending halt gate (called when HALT_GATE_REQUEST arrives). */
  setPendingGate: (gate: HaltGateRequest | null) => void
  /** Send the user's response to the halt gate. */
  respondToGate: (
    threadId: string,
    runId: string,
    gateId: string,
    choice: string,
    customInput?: string,
  ) => Promise<void>
  /** True while the response is being sent. */
  isResponding: boolean
}

export function useHaltGate(): UseHaltGateReturn {
  const [pendingGate, setPendingGate] = useState<HaltGateRequest | null>(null)
  const [isResponding, setIsResponding] = useState(false)

  const respondToGate = useCallback(
    async (
      threadId: string,
      runId: string,
      gateId: string,
      choice: string,
      customInput?: string,
    ) => {
      setIsResponding(true)
      try {
        const token = getAccessToken()
        const base = resolveApiBase()
        const response = await fetch(`${base}/api/agents/halt-gate/respond`, {
          method: 'POST',
          headers: {
            ...buildHeaders(token),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            threadId,
            runId,
            gateId,
            choice,
            customInput: customInput ?? null,
          } satisfies HaltGateResponsePayload),
        })

        if (!response.ok) {
          throw new Error(`Failed to respond to halt gate: ${response.status}`)
        }

        // Clear the pending gate after successful response
        setPendingGate(null)
      } finally {
        setIsResponding(false)
      }
    },
    [],
  )

  return { pendingGate, setPendingGate, respondToGate, isResponding }
}
