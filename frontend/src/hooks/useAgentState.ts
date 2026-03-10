/**
 * useAgentState — shared state synchronization between agent and frontend.
 *
 * Manages the local copy of the agent's shared state, applying
 * STATE_SNAPSHOT (full sync) and STATE_DELTA (JSON Patch) updates
 * as they arrive via SSE events.
 *
 * State persists in sessionStorage for navigation resilience.
 */

import { useState, useCallback, useEffect, useRef } from 'react'
import type { AgentSharedState, JsonPatchOperation } from '../types/agui'

const STORAGE_KEY = 'agent_shared_state'

const DEFAULT_STATE: AgentSharedState = {
  currentPhase: 'strategy',
  activeSection: null,
  docCompleteness: {},
  enrichmentStatus: 'idle',
  contextSummary: '',
  haltGatesPending: [],
  components: [],
}

/**
 * Apply RFC 6902 JSON Patch operations to a state object.
 * Supports top-level replace, add, and remove operations.
 */
function applyPatch(
  state: AgentSharedState,
  operations: JsonPatchOperation[],
): AgentSharedState {
  const result = { ...state }

  for (const op of operations) {
    // Strip leading slash to get the top-level key
    const key = op.path.replace(/^\//, '') as keyof AgentSharedState

    if (!key) continue

    if (op.op === 'replace' || op.op === 'add') {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ;(result as any)[key] = op.value
    } else if (op.op === 'remove') {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (result as any)[key]
    }
  }

  return result
}

/** Load persisted state from sessionStorage, or return default. */
function loadPersistedState(): AgentSharedState {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY)
    if (stored) {
      return { ...DEFAULT_STATE, ...JSON.parse(stored) }
    }
  } catch {
    // Ignore parse errors
  }
  return { ...DEFAULT_STATE }
}

interface UseAgentStateReturn {
  /** Current shared state. */
  state: AgentSharedState
  /** Apply a full state snapshot (STATE_SNAPSHOT event). */
  applySnapshot: (snapshot: AgentSharedState) => void
  /** Apply JSON Patch delta operations (STATE_DELTA event). */
  applyDelta: (operations: JsonPatchOperation[]) => void
  /** Select a specific state value by key. */
  selectState: <K extends keyof AgentSharedState>(key: K) => AgentSharedState[K]
  /** Reset state to defaults. */
  resetState: () => void
}

export function useAgentState(): UseAgentStateReturn {
  const [state, setState] = useState<AgentSharedState>(loadPersistedState)
  const stateRef = useRef(state)
  stateRef.current = state

  // Persist state changes to sessionStorage
  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    } catch {
      // Ignore storage errors (e.g., quota exceeded)
    }
  }, [state])

  const applySnapshot = useCallback((snapshot: AgentSharedState) => {
    setState({ ...DEFAULT_STATE, ...snapshot })
  }, [])

  const applyDelta = useCallback((operations: JsonPatchOperation[]) => {
    setState((prev) => applyPatch(prev, operations))
  }, [])

  const selectState = useCallback(
    <K extends keyof AgentSharedState>(key: K): AgentSharedState[K] => {
      return stateRef.current[key]
    },
    [],
  )

  const resetState = useCallback(() => {
    setState({ ...DEFAULT_STATE })
    try {
      sessionStorage.removeItem(STORAGE_KEY)
    } catch {
      // Ignore
    }
  }, [])

  return { state, applySnapshot, applyDelta, selectState, resetState }
}
