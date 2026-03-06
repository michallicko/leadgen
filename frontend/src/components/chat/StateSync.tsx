/**
 * StateSync — provider component that manages agent state synchronization.
 *
 * Wraps children with a context that provides the shared agent state.
 * Processes STATE_SNAPSHOT and STATE_DELTA events from the SSE stream
 * and keeps the local state in sync.
 */

import { createContext, useContext, type ReactNode } from 'react'
import { useAgentState } from '../../hooks/useAgentState'
import type { AgentSharedState, JsonPatchOperation } from '../../types/agui'

interface StateSyncContextValue {
  state: AgentSharedState
  applySnapshot: (snapshot: AgentSharedState) => void
  applyDelta: (operations: JsonPatchOperation[]) => void
  resetState: () => void
}

const StateSyncContext = createContext<StateSyncContextValue | null>(null)

interface StateSyncProviderProps {
  children: ReactNode
}

/**
 * Provider that manages agent shared state and exposes it to descendants.
 *
 * The ChatProvider (or useSSE callbacks) should call applySnapshot/applyDelta
 * when STATE_SNAPSHOT/STATE_DELTA events arrive.
 */
export function StateSyncProvider({ children }: StateSyncProviderProps) {
  const { state, applySnapshot, applyDelta, resetState } = useAgentState()

  return (
    <StateSyncContext.Provider value={{ state, applySnapshot, applyDelta, resetState }}>
      {children}
    </StateSyncContext.Provider>
  )
}

/**
 * Hook to access the synchronized agent state.
 *
 * Must be used within a StateSyncProvider.
 */
export function useStateSync(): StateSyncContextValue {
  const ctx = useContext(StateSyncContext)
  if (!ctx) {
    throw new Error('useStateSync must be used within a StateSyncProvider')
  }
  return ctx
}
