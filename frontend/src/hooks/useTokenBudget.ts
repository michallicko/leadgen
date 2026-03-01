/**
 * Hook to fetch and expose token budget status for the current namespace.
 * Polls every 60 seconds. Used by AppShell for warning banners
 * and by the credits dashboard.
 */

import { useEffect, useState, useCallback } from 'react'
import { apiFetch } from '../api/client'
import { useAuth } from './useAuth'

export interface BudgetStatus {
  total_budget: number
  used_credits: number
  reserved_credits: number
  remaining_credits: number
  usage_pct: number
  enforcement_mode: 'monitor' | 'soft' | 'hard'
  alert_threshold_pct: number
  next_reset_at: string | null
}

interface TokenBudgetState {
  budget: BudgetStatus | null
  loading: boolean
  /** 'none' | 'warning' | 'exceeded' | 'hard_blocked' */
  alertLevel: 'none' | 'warning' | 'exceeded' | 'hard_blocked'
}

const POLL_INTERVAL = 60_000 // 60 seconds

export function useTokenBudget(): TokenBudgetState {
  const { hasRole, isAuthenticated } = useAuth()
  const [budget, setBudget] = useState<BudgetStatus | null>(null)
  const [loading, setLoading] = useState(true)

  const isAdmin = hasRole('admin')

  const fetchStatus = useCallback(async () => {
    if (!isAuthenticated || !isAdmin) {
      setLoading(false)
      return
    }
    try {
      const resp = await apiFetch<{ budget: BudgetStatus | null }>('/admin/tokens/status')
      setBudget(resp.budget)
    } catch {
      // Silently fail — banner just won't show
    } finally {
      setLoading(false)
    }
  }, [isAuthenticated, isAdmin])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, POLL_INTERVAL)
    return () => clearInterval(interval)
  }, [fetchStatus])

  // Compute alert level
  let alertLevel: TokenBudgetState['alertLevel'] = 'none'
  if (budget) {
    const pct = budget.usage_pct
    const threshold = budget.alert_threshold_pct

    if (budget.enforcement_mode === 'hard' && pct >= 100) {
      alertLevel = 'hard_blocked'
    } else if (pct >= 100) {
      alertLevel = 'exceeded'
    } else if (pct >= threshold) {
      alertLevel = 'warning'
    }
  }

  return { budget, loading, alertLevel }
}
