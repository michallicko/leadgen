import { useState, useCallback } from 'react'
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
  const [searchParams, setSearchParams] = useSearchParams()
  const openId = searchParams.get('open')

  const [stack, setStack] = useState<EntityRef[]>(() =>
    openId ? [{ type: defaultType, id: openId }] : []
  )

  const syncUrl = useCallback((newStack: EntityRef[]) => {
    if (newStack.length > 0) {
      setSearchParams({ open: newStack[newStack.length - 1].id }, { replace: true })
    } else {
      const next = new URLSearchParams(searchParams)
      next.delete('open')
      setSearchParams(next, { replace: true })
    }
  }, [searchParams, setSearchParams])

  const open = useCallback((type: EntityType, id: string) => {
    const newStack = [{ type, id }]
    setStack(newStack)
    syncUrl(newStack)
  }, [syncUrl])

  const push = useCallback((type: EntityType, id: string) => {
    setStack((prev) => {
      const newStack = [...prev, { type, id }]
      syncUrl(newStack)
      return newStack
    })
  }, [syncUrl])

  const pop = useCallback(() => {
    setStack((prev) => {
      if (prev.length <= 1) return prev
      const newStack = prev.slice(0, -1)
      syncUrl(newStack)
      return newStack
    })
  }, [syncUrl])

  const close = useCallback(() => {
    setStack([])
    syncUrl([])
  }, [syncUrl])

  const current = stack.length > 0 ? stack[stack.length - 1] : null

  return { current, depth: stack.length, open, push, pop, close }
}
