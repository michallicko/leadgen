import { useState } from 'react'
import { useAuth } from '../../hooks/useAuth'
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
        {isSuperAdmin && (
          <NamespacesCard onNamespaceCreated={() => setRefreshKey((k) => k + 1)} />
        )}
        <UsersCard isSuperAdmin={isSuperAdmin} refreshKey={refreshKey} />
      </div>
    </div>
  )
}
