import { useState, useCallback } from 'react'

/**
 * Persist a value in localStorage with a typed React state interface.
 * Falls back to `initial` if key is missing or JSON parse fails.
 */
export function useLocalStorage<T>(key: string, initial: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key)
      return stored !== null ? (JSON.parse(stored) as T) : initial
    } catch {
      return initial
    }
  })

  const set = useCallback(
    (v: T) => {
      setValue(v)
      try {
        localStorage.setItem(key, JSON.stringify(v))
      } catch {
        // localStorage full or blocked — silently ignore
      }
    },
    [key],
  )

  return [value, set]
}
