import { useState, useCallback, useEffect } from 'react'
import type { ChatFilterPayload } from '../components/ui/ChatFilterSyncBar'

/**
 * Hook that listens for custom events from the chat system.
 * The chat agent dispatches 'chat:filter-sync' events on window
 * when it wants to apply filters to the contacts table.
 */
export function useChatFilterSync() {
  const [pending, setPending] = useState<ChatFilterPayload | null>(null)

  useEffect(() => {
    const handler = (e: CustomEvent<ChatFilterPayload>) => {
      setPending(e.detail)
    }
    window.addEventListener('chat:filter-sync', handler as EventListener)
    return () => window.removeEventListener('chat:filter-sync', handler as EventListener)
  }, [])

  const dismiss = useCallback(() => setPending(null), [])

  return { pending, dismiss }
}
