/**
 * Single API client — replaces 7 duplicated apiFetch implementations.
 * Handles auth headers, namespace header, token refresh, and error normalization.
 */

import {
  getAccessToken,
  getRefreshToken,
  isTokenExpired,
  storeTokens,
  clearTokens,
  getNamespaceFromPath,
} from '../lib/auth'

function resolveApiBase(): string {
  const env = import.meta.env.VITE_API_BASE
  if (env) return env
  const rev = new URLSearchParams(window.location.search).get('rev')
  return rev ? `/api-rev-${rev}/api` : '/api'
}

const API_BASE = resolveApiBase()

export class ApiError extends Error {
  status: number
  code?: string
  details?: Record<string, unknown>

  constructor(
    message: string,
    status: number,
    code?: string,
    details?: Record<string, unknown>,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

async function refreshAccessToken(): Promise<string> {
  const refreshToken = getRefreshToken()
  if (!refreshToken || isTokenExpired(refreshToken)) {
    throw new ApiError('Session expired', 401)
  }

  const resp = await fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })

  if (!resp.ok) {
    clearTokens()
    throw new ApiError('Session expired', 401)
  }

  const data = (await resp.json()) as { access_token: string }
  storeTokens(data.access_token)
  return data.access_token
}

function buildHeaders(token: string | null): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const ns = getNamespaceFromPath()
  if (ns) {
    headers['X-Namespace'] = ns
  }

  return headers
}

/**
 * Core fetch wrapper. Automatically:
 * - Attaches Bearer token and X-Namespace header
 * - Refreshes expired access tokens (once)
 * - Throws typed ApiError on failure
 */
export async function apiFetch<T = unknown>(
  path: string,
  options: {
    method?: string
    body?: unknown
    params?: Record<string, string>
  } = {},
): Promise<T> {
  const { method = 'GET', body, params } = options

  let url = `${API_BASE}${path}`
  if (params) {
    const qs = new URLSearchParams(params)
    url += `?${qs.toString()}`
  }

  let token = getAccessToken()

  // Auto-refresh expired access token
  if (token && isTokenExpired(token)) {
    try {
      token = await refreshAccessToken()
    } catch {
      clearTokens()
      window.location.href = '/'
      throw new ApiError('Session expired', 401)
    }
  }

  const resp = await fetch(url, {
    method,
    headers: buildHeaders(token),
    body: body ? JSON.stringify(body) : undefined,
  })

  // 401 — try one refresh, then give up
  if (resp.status === 401 && token) {
    try {
      const newToken = await refreshAccessToken()
      const retry = await fetch(url, {
        method,
        headers: buildHeaders(newToken),
        body: body ? JSON.stringify(body) : undefined,
      })
      if (retry.ok) {
        return (await retry.json()) as T
      }
    } catch {
      // refresh failed — fall through to error handling
    }
    clearTokens()
    window.location.href = '/'
    throw new ApiError('Session expired', 401)
  }

  if (!resp.ok) {
    let errorBody: { error?: string; code?: string; details?: Record<string, unknown> } = {}
    try {
      errorBody = (await resp.json()) as typeof errorBody
    } catch {
      // non-JSON error
    }
    throw new ApiError(
      errorBody.error ?? `Request failed (${resp.status})`,
      resp.status,
      errorBody.code,
      errorBody.details,
    )
  }

  // Handle 204 No Content
  if (resp.status === 204) {
    return undefined as T
  }

  return (await resp.json()) as T
}

/**
 * Upload wrapper for FormData (file uploads).
 * Same auth/refresh/error handling as apiFetch, but does NOT set Content-Type
 * (browser sets it automatically with the multipart boundary).
 */
export async function apiUpload<T = unknown>(
  path: string,
  formData: FormData,
): Promise<T> {
  const url = `${API_BASE}${path}`

  let token = getAccessToken()

  // Auto-refresh expired access token
  if (token && isTokenExpired(token)) {
    try {
      token = await refreshAccessToken()
    } catch {
      clearTokens()
      window.location.href = '/'
      throw new ApiError('Session expired', 401)
    }
  }

  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const ns = getNamespaceFromPath()
  if (ns) {
    headers['X-Namespace'] = ns
  }

  const resp = await fetch(url, {
    method: 'POST',
    headers,
    body: formData,
  })

  // 401 — try one refresh, then give up
  if (resp.status === 401 && token) {
    try {
      const newToken = await refreshAccessToken()
      const retryHeaders: Record<string, string> = {
        Authorization: `Bearer ${newToken}`,
      }
      if (ns) {
        retryHeaders['X-Namespace'] = ns
      }
      const retry = await fetch(url, {
        method: 'POST',
        headers: retryHeaders,
        body: formData,
      })
      if (retry.ok) {
        return (await retry.json()) as T
      }
    } catch {
      // refresh failed — fall through to error handling
    }
    clearTokens()
    window.location.href = '/'
    throw new ApiError('Session expired', 401)
  }

  if (!resp.ok) {
    let errorBody: { error?: string; code?: string; details?: Record<string, unknown> } = {}
    try {
      errorBody = (await resp.json()) as typeof errorBody
    } catch {
      // non-JSON error
    }
    throw new ApiError(
      errorBody.error ?? `Request failed (${resp.status})`,
      resp.status,
      errorBody.code,
      errorBody.details,
    )
  }

  if (resp.status === 204) {
    return undefined as T
  }

  return (await resp.json()) as T
}

/**
 * Login — returns user data and stores tokens.
 */
export async function login(
  email: string,
  password: string,
): Promise<{
  access_token: string
  refresh_token: string
  user: import('../lib/auth').StoredUser
}> {
  const resp = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })

  if (!resp.ok) {
    const body = (await resp.json().catch(() => ({}))) as { error?: string }
    throw new ApiError(body.error ?? 'Login failed', resp.status)
  }

  return (await resp.json()) as {
    access_token: string
    refresh_token: string
    user: import('../lib/auth').StoredUser
  }
}
