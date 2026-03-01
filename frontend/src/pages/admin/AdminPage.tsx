import { useState } from 'react'
import { Link } from 'react-router'
import { useAuth } from '../../hooks/useAuth'
import { useTokenBudget } from '../../hooks/useTokenBudget'
import { useNamespace } from '../../hooks/useNamespace'
import { NamespacesCard } from './NamespacesCard'
import { UsersCard } from './UsersCard'

export function AdminPage() {
  const { hasRole, user } = useAuth()
  const [refreshKey, setRefreshKey] = useState(0)

  if (!hasRole('admin')) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-text-muted text-sm">You do not have admin access.</p>
      </div>
    )
  }

  const isSuperAdmin = user?.is_super_admin ?? false

  return (
    <div className="max-w-[1060px] mx-auto">
      <div className="mb-5">
        <h1 className="font-title text-[1.3rem] font-semibold tracking-tight mb-1.5">
          Administration
        </h1>
        <p className="text-text-muted text-sm">
          Manage namespaces, users, and roles.
        </p>
      </div>

      <div className="flex flex-col gap-4">
        <CreditsCard />
        {isSuperAdmin && (
          <NamespacesCard onNamespaceCreated={() => setRefreshKey((k) => k + 1)} />
        )}
        <UsersCard isSuperAdmin={isSuperAdmin} refreshKey={refreshKey} />
      </div>
    </div>
  )
}



function CreditsCard() {
  const { budget, loading } = useTokenBudget()
  const namespace = useNamespace()

  const formatCredits = (n: number) => {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
    if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
    return n.toLocaleString()
  }

  return (
    <div className="bg-surface border border-border rounded-lg p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-title text-[1rem] font-semibold tracking-tight">Credits</h2>
        <Link
          to={`/${namespace}/admin/tokens`}
          className="text-sm text-accent hover:underline"
        >
          View dashboard
        </Link>
      </div>

      {loading ? (
        <div className="h-8 bg-surface-alt rounded animate-pulse" />
      ) : budget ? (
        <div className="flex items-center gap-4">
          {/* Mini gauge */}
          <div className="relative w-12 h-12">
            <svg viewBox="0 0 48 48" className="w-12 h-12">
              <circle cx="24" cy="24" r="18" fill="none" stroke="currentColor" strokeWidth="4" className="text-surface-alt" />
              <circle
                cx="24" cy="24" r="18" fill="none" strokeWidth="4"
                stroke={budget.usage_pct >= 95 ? '#ef4444' : budget.usage_pct >= 80 ? '#f97316' : '#22c55e'}
                strokeDasharray={`${Math.min(budget.usage_pct, 100) * 1.13} 113`}
                strokeLinecap="round"
                transform="rotate(-90 24 24)"
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center text-[0.6rem] font-semibold text-text">
              {Math.round(budget.usage_pct)}%
            </span>
          </div>

          <div className="text-sm text-text-muted">
            <span className="font-medium text-text">{formatCredits(budget.used_credits)}</span>
            {' / '}
            {formatCredits(budget.total_budget)} credits used
          </div>
        </div>
      ) : (
        <p className="text-sm text-text-muted">
          No budget configured — all operations monitored but unlimited.
        </p>
      )}
    </div>
  )
}
