/**
 * App shell — wraps authenticated pages with nav + container.
 */

import { Outlet, Navigate, useParams } from 'react-router'
import { useAuth } from '../../hooks/useAuth'
import { getDefaultNamespace } from '../../lib/auth'
import { AppNav } from './AppNav'

export function AppShell() {
  const { isAuthenticated, isLoading, user } = useAuth()
  const { namespace } = useParams<{ namespace: string }>()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-8 h-8 border-2 border-border border-t-accent rounded-full animate-spin" />
      </div>
    )
  }

  if (!isAuthenticated) {
    const returnPath = window.location.pathname + window.location.search
    return <Navigate to={`/?return=${encodeURIComponent(returnPath)}`} replace />
  }

  // If no namespace in URL but user is authenticated, redirect to default
  if (!namespace && user) {
    const defaultNs = getDefaultNamespace(user)
    if (defaultNs) {
      return <Navigate to={`/${defaultNs}/contacts`} replace />
    }
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <AppNav />
      <div className="flex-1 min-h-0 px-3 sm:px-5 py-3">
        <Outlet />
      </div>
    </div>
  )
}
