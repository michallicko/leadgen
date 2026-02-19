/**
 * Staging revision tracking — persists ?rev= across SPA navigation.
 *
 * The ?rev= query param tells the frontend to route API calls to a specific
 * revision container on staging (e.g., /api-rev-abc1234/api instead of /api).
 *
 * sessionStorage keeps the revision sticky within a browser tab, surviving
 * React Router navigations that would otherwise drop the query param.
 */

const SESSION_KEY = 'lg_rev'

/**
 * Get the active revision: URL param takes priority, then sessionStorage.
 * When found in URL, auto-persists to sessionStorage.
 */
export function getRevision(): string | null {
  const urlRev = new URLSearchParams(window.location.search).get('rev')
  if (urlRev) {
    sessionStorage.setItem(SESSION_KEY, urlRev)
    return urlRev
  }
  return sessionStorage.getItem(SESSION_KEY)
}

/**
 * Clear the stored revision (e.g., when dismissing the revision indicator).
 */
export function clearRevision(): void {
  sessionStorage.removeItem(SESSION_KEY)
}

/**
 * Append ?rev= to a path if a revision is active.
 */
export function withRev(path: string): string {
  const rev = getRevision()
  if (!rev) return path
  const separator = path.includes('?') ? '&' : '?'
  return `${path}${separator}rev=${rev}`
}
