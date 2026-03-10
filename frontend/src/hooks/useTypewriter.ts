import { useState, useEffect, useRef } from 'react'

/**
 * useTypewriter -- reveals characters one at a time with a stagger delay.
 *
 * Takes the full text as input (which may grow as new chunks arrive from SSE)
 * and returns the currently visible portion. When new chunks arrive, continues
 * revealing from where it left off.
 *
 * @param text  The full accumulated text to reveal
 * @param speed Milliseconds between each character reveal (default 30)
 * @returns     The currently visible portion of the text
 */
export function useTypewriter(text: string, speed: number = 30): string {
  const [displayed, setDisplayed] = useState('')
  const indexRef = useRef(0)

  useEffect(() => {
    if (indexRef.current >= text.length) return

    const timer = setInterval(() => {
      indexRef.current++
      setDisplayed(text.slice(0, indexRef.current))
      if (indexRef.current >= text.length) clearInterval(timer)
    }, speed)

    return () => clearInterval(timer)
  }, [text, speed])

  // Reset when text is cleared (streaming ended)
  useEffect(() => {
    if (!text) {
      indexRef.current = 0
      setDisplayed('')
    }
  }, [text])

  return displayed
}
