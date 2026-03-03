import { type Page } from '@playwright/test'
import { BASE } from './auth'

/** Navigate to a namespaced page. */
export async function gotoNamespacedPage(page: Page, namespace: string, path = '') {
  const url = `${BASE}/${namespace}/${path}`.replace(/\/+$/, '/')
  await page.goto(url)
}

/** Get the current namespace from the URL path. */
export function getNamespaceFromUrl(url: string): string | null {
  const match = url.match(/visionvolve\.com\/([^/]+)/)
  return match ? match[1] : null
}
