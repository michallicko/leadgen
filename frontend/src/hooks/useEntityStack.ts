import { useState, useCallback, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router'

export type EntityType = 'company' | 'contact'

export interface EntityRef {
  type: EntityType
  id: string
}

export interface EntityStack {
  /** Current entity at top of stack (null = modal closed) */
  current: EntityRef | null
  /** Number of entries in the stack */
  depth: number
  /** Open an entity (replaces stack with single entry). Use for initial open from table row. */
  open: (type: EntityType, id: string) => void
  /** Push a related entity onto the stack (for cross-entity navigation). */
  push: (type: EntityType, id: string) => void
  /** Pop back to previous entity. */
  pop: () => void
  /** Close modal entirely (clears stack). */
  close: () => void
}

/**
 * Modal navigation stack. Syncs the top-of-stack entity ID with ?open= URL param.
 * @param defaultType - the entity type for the page (used when reading ?open= from URL)
 */
export function useEntityStack(defaultType: EntityType): EntityStack {
  const [, setSearchParams] = useSearchParams()

  const [stack, setStack] = useState<EntityRef[]>(() => {
    const params = new URLSearchParams(window.location.search)
    const id = params.get('open')
    return id ? [{ type: defaultType, id }] : []
  })

  // Sync URL whenever stack changes
  const isFirstRender = useRef(true)
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false
      return // Don't sync on mount — URL already has the correct value
    }
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      const top = stack[stack.length - 1]
      if (top) {
        next.set('open', top.id)
      } else {
        next.delete('open')
      }
      return next
    }, { replace: true })
  }, [stack, setSearchParams])

  const open = useCallback((type: EntityType, id: string) => {
    setStack([{ type, id }])
  }, [])

  const push = useCallback((type: EntityType, id: string) => {
    setStack((prev) => {
      const top = prev[prev.length - 1]
      if (top && top.type === type && top.id === id) return prev
      return [...prev, { type, id }]
    })
  }, [])

  const pop = useCallback(() => {
    setStack((prev) => {
      if (prev.length <= 1) return prev
      return prev.slice(0, -1)
    })
  }, [])

  const close = useCallback(() => {
    setStack([])
  }, [])

  const current = stack.length > 0 ? stack[stack.length - 1] : null

  return { current, depth: stack.length, open, push, pop, close }
}
