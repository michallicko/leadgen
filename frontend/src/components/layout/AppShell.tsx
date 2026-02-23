/**
 * App shell — wraps authenticated pages with nav + container.
 */

import { Outlet, Navigate, useParams } from 'react-router'
import { useAuth } from '../../hooks/useAuth'
import { getDefaultNamespace } from '../../lib/auth'
import { AppNav } from './AppNav'
import { ChatPanel } from '../chat/ChatPanel'
import { useChatContext } from '../../providers/ChatProvider'

// ---- Mobile floating action button for chat ----

function MobileFAB() {
  const { toggleChat, isOnPlaybookPage } = useChatContext()

  // Don't show on playbook page (inline chat) or on desktop (nav button)
  if (isOnPlaybookPage) return null

  return (
    <button
      onClick={toggleChat}
      className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-accent text-white shadow-lg z-[28] flex items-center justify-center md:hidden"
      aria-label="Toggle AI Chat"
    >
      <svg
        viewBox="0 0 24 24"
        className="w-6 h-6"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    </button>
  )
}

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
      <div className="flex-1 min-h-0 overflow-y-auto px-3 sm:px-5 py-3">
        <Outlet />
      </div>
      <ChatPanel />
      <MobileFAB />
    </div>
  )
}
