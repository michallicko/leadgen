/**
 * App shell — wraps authenticated pages with nav + container.
 */

import { useState } from 'react'
import { Outlet, Navigate, useParams } from 'react-router'
import { useAuth } from '../../hooks/useAuth'
import { useTokenBudget } from '../../hooks/useTokenBudget'
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
      <BudgetWarningBanner />
      <div className="flex-1 min-h-0 overflow-y-auto px-3 sm:px-5 py-3">
        <Outlet />
      </div>
      <ChatPanel />
      <MobileFAB />
    </div>
  )
}


// ---- Budget warning banner ----

function BudgetWarningBanner() {
  const { alertLevel, budget } = useTokenBudget()
  const [dismissed, setDismissed] = useState<string | null>(
    () => sessionStorage.getItem('budget_banner_dismissed')
  )

  if (alertLevel === 'none' || !budget) return null

  // Allow dismissing per level — re-show if level escalates
  if (dismissed === alertLevel) return null

  const handleDismiss = () => {
    sessionStorage.setItem('budget_banner_dismissed', alertLevel)
    setDismissed(alertLevel)
  }

  const pct = Math.round(budget.usage_pct)
  let bg: string
  let message: string

  switch (alertLevel) {
    case 'warning':
      bg = 'bg-yellow-50 border-yellow-300 text-yellow-800'
      message = `Your workspace has used ${pct}% of its credit budget this period.`
      break
    case 'exceeded':
      bg = 'bg-orange-50 border-orange-300 text-orange-800'
      message = 'Credit budget exceeded. Operations may be limited.'
      break
    case 'hard_blocked':
      bg = 'bg-red-50 border-red-300 text-red-800'
      message = 'Credit budget reached. AI operations are paused. Contact your admin.'
      break
    default:
      return null
  }

  return (
    <div className={`${bg} border-b px-4 py-2 text-sm flex items-center justify-between`}>
      <span>{message}</span>
      <button
        onClick={handleDismiss}
        className="ml-3 text-current opacity-60 hover:opacity-100 text-lg leading-none"
        aria-label="Dismiss"
      >
        x
      </button>
    </div>
  )
}
