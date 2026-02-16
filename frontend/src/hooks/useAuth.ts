/**
 * Auth hook — manages login state, token lifecycle, and user context.
 * Ported from dashboard/auth.js IIFE to React context + hook.
 */

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { createElement } from 'react'
import {
  getAccessToken,
  getRefreshToken,
  isTokenExpired,
  storeTokens,
  storeUser,
  clearTokens,
  getStoredUser,
  getUserRole,
  hasMinRole,
  type StoredUser,
  type Role,
} from '../lib/auth'
import { login as apiLogin } from '../api/client'

interface AuthState {
  user: StoredUser | null
  isAuthenticated: boolean
  isLoading: boolean
  role: Role
}

interface AuthActions {
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  hasRole: (minRole: Role) => boolean
}

type AuthContextValue = AuthState & AuthActions

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
    role: 'viewer',
  })
  const [loginError, setLoginError] = useState<string | null>(null)

  // Check existing tokens on mount
  useEffect(() => {
    const token = getAccessToken()
    const refreshToken = getRefreshToken()

    if (token && !isTokenExpired(token)) {
      const user = getStoredUser()
      if (user) {
        setState({
          user,
          isAuthenticated: true,
          isLoading: false,
          role: getUserRole(user),
        })
        return
      }
    }

    // Try refresh
    if (refreshToken && !isTokenExpired(refreshToken)) {
      fetch('/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
        .then((r) => {
          if (!r.ok) throw new Error('Refresh failed')
          return r.json() as Promise<{ access_token: string }>
        })
        .then((data) => {
          storeTokens(data.access_token)
          const user = getStoredUser()
          setState({
            user,
            isAuthenticated: !!user,
            isLoading: false,
            role: getUserRole(user),
          })
        })
        .catch(() => {
          clearTokens()
          setState({ user: null, isAuthenticated: false, isLoading: false, role: 'viewer' })
        })
      return
    }

    // No valid tokens
    clearTokens()
    setState({ user: null, isAuthenticated: false, isLoading: false, role: 'viewer' })
  }, [])

  // Periodic token check (every 5 min)
  useEffect(() => {
    if (!state.isAuthenticated) return
    const interval = setInterval(() => {
      const token = getAccessToken()
      if (!token || isTokenExpired(token)) {
        const refresh = getRefreshToken()
        if (refresh && !isTokenExpired(refresh)) {
          fetch('/api/auth/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refresh }),
          })
            .then((r) => {
              if (!r.ok) throw new Error('Refresh failed')
              return r.json() as Promise<{ access_token: string }>
            })
            .then((data) => storeTokens(data.access_token))
            .catch(() => {
              clearTokens()
              setState({ user: null, isAuthenticated: false, isLoading: false, role: 'viewer' })
            })
        } else {
          clearTokens()
          setState({ user: null, isAuthenticated: false, isLoading: false, role: 'viewer' })
        }
      }
    }, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [state.isAuthenticated])

  const login = useCallback(async (email: string, password: string) => {
    setLoginError(null)
    const data = await apiLogin(email, password)
    storeTokens(data.access_token, data.refresh_token)
    storeUser(data.user)
    setState({
      user: data.user,
      isAuthenticated: true,
      isLoading: false,
      role: getUserRole(data.user),
    })
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setState({ user: null, isAuthenticated: false, isLoading: false, role: 'viewer' })
    window.location.href = '/'
  }, [])

  const hasRoleFn = useCallback(
    (minRole: Role) => hasMinRole(state.role, minRole),
    [state.role],
  )

  const value: AuthContextValue = {
    ...state,
    login,
    logout,
    hasRole: hasRoleFn,
  }

  // Expose loginError for the login page if needed
  void loginError

  return createElement(AuthContext.Provider, { value }, children)
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
