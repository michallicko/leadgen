import { useCallback } from 'react'
import { useLocalStorage } from './useLocalStorage'
import type { ColumnDef } from '../config/columns'

/**
 * Manages column visibility with localStorage persistence.
 * Falls back to `defaultVisible` from column definitions if no saved state exists.
 */
export function useColumnVisibility<T>(
  storageKey: string,
  allColumns: ColumnDef<T>[],
): [string[], (keys: string[]) => void, () => void] {
  const defaultKeys = allColumns
    .filter((c) => c.defaultVisible !== false)
    .map((c) => c.key)

  const [visibleKeys, setVisibleKeys] = useLocalStorage<string[]>(
    storageKey,
    defaultKeys,
  )

  const resetToDefaults = useCallback(() => {
    setVisibleKeys(defaultKeys)
  }, [defaultKeys, setVisibleKeys])

  return [visibleKeys, setVisibleKeys, resetToDefaults]
}
