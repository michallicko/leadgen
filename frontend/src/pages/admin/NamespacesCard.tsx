import { useState, useRef } from 'react'
import { useNamespaces, useUpdateNamespace } from '../../api/queries/useAdmin'
import { CreateNamespaceModal } from './CreateNamespaceModal'

function formatDate(iso: string | null): string {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

interface NamespacesCardProps {
  onNamespaceCreated: () => void
}

export function NamespacesCard({ onNamespaceCreated }: NamespacesCardProps) {
  const { data: namespaces, isLoading } = useNamespaces()
  const updateNamespace = useUpdateNamespace()
  const [showCreateModal, setShowCreateModal] = useState(false)

  return (
    <div className="bg-surface border border-border rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-title text-xs font-semibold uppercase tracking-widest text-text-muted">
          Namespaces
        </h2>
        <button
          onClick={() => setShowCreateModal(true)}
          className="bg-accent-cyan text-bg font-semibold px-4 py-2 rounded-md hover:opacity-90 transition-opacity text-sm"
        >
          + Create Namespace
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-8">
          <div className="w-5 h-5 border-2 border-border border-t-accent rounded-full animate-spin" />
        </div>
      ) : !namespaces || namespaces.length === 0 ? (
        <p className="text-center py-8 text-text-muted text-sm">No namespaces found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th className="text-left px-2.5 py-2 text-text-muted font-medium text-xs uppercase tracking-wider border-b border-border">Name</th>
                <th className="text-left px-2.5 py-2 text-text-muted font-medium text-xs uppercase tracking-wider border-b border-border">Slug</th>
                <th className="text-left px-2.5 py-2 text-text-muted font-medium text-xs uppercase tracking-wider border-b border-border">Domain</th>
                <th className="text-left px-2.5 py-2 text-text-muted font-medium text-xs uppercase tracking-wider border-b border-border">Status</th>
                <th className="text-left px-2.5 py-2 text-text-muted font-medium text-xs uppercase tracking-wider border-b border-border">Created</th>
                <th className="text-left px-2.5 py-2 text-text-muted font-medium text-xs uppercase tracking-wider border-b border-border">Actions</th>
              </tr>
            </thead>
            <tbody>
              {namespaces.map((ns) => (
                <NamespaceRow
                  key={ns.id}
                  namespace={ns}
                  onUpdate={(data) => updateNamespace.mutate({ id: ns.id, ...data })}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CreateNamespaceModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={onNamespaceCreated}
      />
    </div>
  )
}

interface NamespaceRowProps {
  namespace: {
    id: string
    name: string
    slug: string
    domain: string | null
    is_active: boolean
    created_at: string
  }
  onUpdate: (data: { name?: string; domain?: string; is_active?: boolean }) => void
}

function NamespaceRow({ namespace, onUpdate }: NamespaceRowProps) {
  const [nameValue, setNameValue] = useState(namespace.name)
  const [domainValue, setDomainValue] = useState(namespace.domain ?? '')
  const nameRef = useRef(namespace.name)
  const domainRef = useRef(namespace.domain ?? '')

  function commitName() {
    if (nameValue !== nameRef.current && nameValue.trim()) {
      nameRef.current = nameValue
      onUpdate({ name: nameValue.trim() })
    }
  }

  function commitDomain() {
    if (domainValue !== domainRef.current) {
      domainRef.current = domainValue
      onUpdate({ domain: domainValue.trim() })
    }
  }

  return (
    <tr className="hover:bg-[rgba(110,44,139,0.04)]">
      <td className="px-2.5 py-2.5 border-b border-border-solid/40">
        <input
          type="text"
          value={nameValue}
          onChange={(e) => setNameValue(e.target.value)}
          onBlur={commitName}
          onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur() }}
          className="bg-transparent border border-transparent focus:bg-surface-alt focus:border-accent-cyan rounded px-2 py-1 text-sm text-text w-[140px] hover:border-border"
        />
      </td>
      <td className="px-2.5 py-2.5 border-b border-border-solid/40">
        <code className="text-xs text-accent-cyan">{namespace.slug}</code>
      </td>
      <td className="px-2.5 py-2.5 border-b border-border-solid/40">
        <input
          type="text"
          value={domainValue}
          onChange={(e) => setDomainValue(e.target.value)}
          onBlur={commitDomain}
          onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur() }}
          placeholder="-"
          className="bg-transparent border border-transparent focus:bg-surface-alt focus:border-accent-cyan rounded px-2 py-1 text-sm text-text w-[140px] hover:border-border"
        />
      </td>
      <td className="px-2.5 py-2.5 border-b border-border-solid/40">
        <label className="relative inline-block w-9 h-5 cursor-pointer">
          <input
            type="checkbox"
            checked={namespace.is_active}
            onChange={() => onUpdate({ is_active: !namespace.is_active })}
            className="sr-only peer"
          />
          <span className="absolute inset-0 rounded-full bg-border-solid transition-colors peer-checked:bg-green-400" />
          <span className="absolute left-0.5 top-0.5 w-4 h-4 rounded-full bg-text transition-transform peer-checked:translate-x-4" />
        </label>
      </td>
      <td className="px-2.5 py-2.5 border-b border-border-solid/40 text-xs text-text-muted">
        {formatDate(namespace.created_at)}
      </td>
      <td className="px-2.5 py-2.5 border-b border-border-solid/40">
        <button
          onClick={() => onUpdate({ is_active: !namespace.is_active })}
          className="text-red-400 hover:text-red-300 text-sm"
        >
          {namespace.is_active ? 'Deactivate' : 'Activate'}
        </button>
      </td>
    </tr>
  )
}
