import { type Page, type APIRequestContext } from '@playwright/test'

export const BASE = process.env.BASE_URL ?? 'https://leadgen-staging.visionvolve.com'
export const API = process.env.API_URL ?? BASE

/** Login via API and inject tokens into localStorage. */
export async function login(page: Page) {
  const resp = await page.request.post(`${API}/api/auth/login`, {
    data: { email: 'test@staging.local', password: 'staging123' },
  })
  const body = await resp.json()
  await page.goto(BASE)
  await page.evaluate(
    ({ access, refresh, user }) => {
      localStorage.setItem('lg_access_token', access)
      localStorage.setItem('lg_refresh_token', refresh)
      localStorage.setItem('lg_user', JSON.stringify(user))
    },
    {
      access: body.access_token,
      refresh: body.refresh_token,
      user: body.user,
    },
  )
  return body
}

/** Get the stored access token from localStorage. */
export async function getToken(page: Page): Promise<string> {
  return (await page.evaluate(() => localStorage.getItem('lg_access_token'))) ?? ''
}

/** Make an authenticated API request. */
export async function apiGet(
  request: APIRequestContext,
  path: string,
  namespace: string,
  token: string,
) {
  return request.get(`${BASE}${path}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'X-Namespace': namespace,
    },
  })
}
