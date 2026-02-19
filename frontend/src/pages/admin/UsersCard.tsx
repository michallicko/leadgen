import { useState, useEffect } from 'react'
import {
  useNamespaces,
  useNamespaceUsers,
  useUpdateUserRole,
  useRemoveUserRole,
  type NamespaceUser,
} from '../../api/queries/useAdmin'
import { useAuth } from '../../hooks/useAuth'
import { AddUserModal } from './AddUserModal'

interface UsersCardProps {
  isSuperAdmin: boolean
  refreshKey: number
}

export function UsersCard({ isSuperAdmin, refreshKey }: UsersCardProps) {
  const { user } = useAuth()
  const { data: namespaces } = useNamespaces()
  const [selectedTenantId, setSelectedTenantId] = useState<string | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)

  const { data: users, isLoading } = useNamespaceUsers(selectedTenantId)
  const updateRole = useUpdateUserRole()
  const removeRole = useRemoveUserRole()

  // When namespaces refresh (e.g. after creation), keep selector if still valid
  useEffect(() => {
    if (!namespaces) return
    if (selectedTenantId && !namespaces.find((n) => n.id === selectedTenantId)) {
      setSelectedTenantId(null)
    }
  }, [namespaces, selectedTenantId, refreshKey])

  // If not super_admin, filter to only user's namespaces
  const availableNamespaces = isSuperAdmin
    ? namespaces ?? []
    : (namespaces ?? []).filter((n) => {
        if (!user?.roles) return false
        return Object.keys(user.roles).includes(n.slug)
      })

  function handleRoleChange(userId: string, role: string) {
    if (!selectedTenantId) return
    updateRole.mutate({ userId, role, tenantId: selectedTenantId })
  }

  function handleRemove(u: NamespaceUser) {
    if (!selectedTenantId) return
    const name = u.display_name || u.email
    if (!window.confirm(`Remove ${name} from this namespace?`)) return
    removeRole.mutate({ userId: u.id, tenantId: selectedTenantId })
  }

  return (
    <div className="bg-surface border border-border rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3.5">
          <h2 className="font-title text-xs font-semibold uppercase tracking-widest text-text-muted">
            Users & Roles
          </h2>
          <select
            value={selectedTenantId ?? ''}
            onChange={(e) => setSelectedTenantId(e.target.value || null)}
            className="bg-bg border border-border rounded-md px-2.5 py-2 text-sm text-text focus:outline-none focus:border-accent-cyan min-w-[200px]"
          >
            <option value="">Select namespace...</option>
            {availableNamespaces.map((n) => (
              <option key={n.id} value={n.id}>
                {n.name} ({n.slug})
              </option>
            ))}
          </select>
        </div>
        {selectedTenantId && (
          <button
            onClick={() => setShowAddModal(true)}
            className="bg-accent-cyan text-bg font-semibold px-4 py-2 rounded-md hover:opacity-90 transition-opacity text-sm"
          >
            + Add User
          </button>
        )}
      </div>

      {!selectedTenantId ? (
        <p className="text-center py-8 text-text-muted text-sm">
          Select a namespace to view users.
        </p>
      ) : isLoading ? (
        <div className="flex justify-center py-8">
          <div className="w-5 h-5 border-2 border-border border-t-accent rounded-full animate-spin" />
        </div>
      ) : !users || users.length === 0 ? (
        <p className="text-center py-8 text-text-muted text-sm">
          No users in this namespace.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th className="text-left px-2.5 py-2 text-text-muted font-medium text-xs uppercase tracking-wider border-b border-border">Name</th>
                <th className="text-left px-2.5 py-2 text-text-muted font-medium text-xs uppercase tracking-wider border-b border-border">Email</th>
                <th className="text-left px-2.5 py-2 text-text-muted font-medium text-xs uppercase tracking-wider border-b border-border">Role</th>
                <th className="text-left px-2.5 py-2 text-text-muted font-medium text-xs uppercase tracking-wider border-b border-border">Status</th>
                <th className="text-left px-2.5 py-2 text-text-muted font-medium text-xs uppercase tracking-wider border-b border-border">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-[rgba(110,44,139,0.04)]">
                  <td className="px-2.5 py-2.5 border-b border-border-solid/40">
                    {u.display_name || '-'}
                  </td>
                  <td className="px-2.5 py-2.5 border-b border-border-solid/40 text-xs text-text-muted">
                    {u.email}
                  </td>
                  <td className="px-2.5 py-2.5 border-b border-border-solid/40">
                    {u.role === 'super_admin' ? (
                      <span className="text-xs text-accent-cyan font-semibold">Super Admin</span>
                    ) : (
                      <select
                        value={u.role}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                        className="bg-bg border border-border rounded px-1.5 py-1 text-xs text-text focus:outline-none focus:border-accent-cyan cursor-pointer"
                      >
                        <option value="viewer">Viewer</option>
                        <option value="editor">Editor</option>
                        <option value="admin">Admin</option>
                      </select>
                    )}
                  </td>
                  <td className="px-2.5 py-2.5 border-b border-border-solid/40">
                    {u.is_active ? (
                      <span className="inline-flex items-center gap-1.5 text-xs">
                        <span className="w-2 h-2 rounded-full bg-green-400" />
                        Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 text-xs text-text-muted">
                        <span className="w-2 h-2 rounded-full bg-text-dim" />
                        Inactive
                      </span>
                    )}
                  </td>
                  <td className="px-2.5 py-2.5 border-b border-border-solid/40">
                    <button
                      onClick={() => handleRemove(u)}
                      className="text-red-400 hover:text-red-300 text-sm"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedTenantId && (
        <AddUserModal
          open={showAddModal}
          onClose={() => setShowAddModal(false)}
          tenantId={selectedTenantId}
        />
      )}
    </div>
  )
}
