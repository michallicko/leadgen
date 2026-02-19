import { useState } from 'react'
import { Modal } from '../../components/ui/Modal'
import { useCreateNamespace, type CreateNamespaceResponse } from '../../api/queries/useAdmin'

function toSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

interface CreateNamespaceModalProps {
  open: boolean
  onClose: () => void
  onCreated: () => void
}

export function CreateNamespaceModal({ open, onClose, onCreated }: CreateNamespaceModalProps) {
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [domain, setDomain] = useState('')
  const [adminEmail, setAdminEmail] = useState('')
  const [slugManuallyEdited, setSlugManuallyEdited] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successData, setSuccessData] = useState<CreateNamespaceResponse | null>(null)
  const [copied, setCopied] = useState(false)

  const createNamespace = useCreateNamespace()

  function reset() {
    setName('')
    setSlug('')
    setDomain('')
    setAdminEmail('')
    setSlugManuallyEdited(false)
    setError(null)
    setSuccessData(null)
    setCopied(false)
  }

  function handleClose() {
    reset()
    onClose()
  }

  function handleNameChange(value: string) {
    setName(value)
    if (!slugManuallyEdited) {
      setSlug(toSlug(value))
    }
  }

  function handleSlugChange(value: string) {
    setSlugManuallyEdited(true)
    setSlug(value)
  }

  function validate(): string | null {
    if (!name.trim()) return 'Name is required.'
    if (!slug.trim()) return 'Slug is required.'
    if (!/^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$/.test(slug)) {
      return 'Slug must be lowercase alphanumeric with hyphens, cannot start or end with a hyphen.'
    }
    return null
  }

  function handleSubmit() {
    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }

    setError(null)

    const payload: { name: string; slug: string; domain?: string; admin_email?: string } = {
      name: name.trim(),
      slug: slug.trim(),
    }
    if (domain.trim()) payload.domain = domain.trim()
    if (adminEmail.trim()) payload.admin_email = adminEmail.trim()

    createNamespace.mutate(payload, {
      onSuccess: (data) => {
        onCreated()
        if (data.admin_user?.temp_password) {
          setSuccessData(data)
        } else {
          handleClose()
        }
      },
      onError: (err) => {
        setError(err instanceof Error ? err.message : 'Failed to create namespace.')
      },
    })
  }

  function handleCopy() {
    if (!successData?.admin_user?.temp_password) return
    navigator.clipboard.writeText(successData.admin_user.temp_password).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  // After success with temp password, show success view
  if (successData?.admin_user?.temp_password) {
    return (
      <Modal
        open={open}
        onClose={handleClose}
        title="Namespace Created"
        actions={
          <button
            onClick={handleClose}
            className="bg-accent-cyan text-bg font-semibold px-4 py-2 rounded-md hover:opacity-90 transition-opacity text-sm"
          >
            Close
          </button>
        }
      >
        <div className="space-y-4">
          <p className="text-green-400 text-sm font-medium">
            Namespace created successfully.
          </p>
          <div>
            <p className="text-xs text-text-muted mb-2">
              Temporary password for {successData.admin_user.email}:
            </p>
            <div className="flex items-center gap-3 bg-surface-alt rounded-md px-3 py-2">
              <code className="flex-1 font-mono text-sm text-accent-cyan break-all">
                {successData.admin_user.temp_password}
              </code>
              <button
                onClick={handleCopy}
                className="border border-border text-text-muted px-3 py-1 rounded-md hover:bg-surface-alt transition-colors text-xs flex-shrink-0"
              >
                {copied ? 'Copied!' : 'Copy'}
              </button>
            </div>
          </div>
        </div>
      </Modal>
    )
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Create Namespace"
      actions={
        <>
          <button
            onClick={handleClose}
            className="border border-border text-text-muted px-4 py-2 rounded-md hover:bg-surface-alt transition-colors text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={createNamespace.isPending}
            className="bg-accent-cyan text-bg font-semibold px-4 py-2 rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
          >
            {createNamespace.isPending ? 'Creating...' : 'Create'}
          </button>
        </>
      }
    >
      <div className="space-y-3.5">
        <div>
          <label className="block text-xs text-text-muted mb-1">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            className="w-full bg-surface-alt border border-border rounded-md px-3 py-2 text-sm text-text placeholder:text-text-dim focus:outline-none focus:border-accent-cyan"
            placeholder="My Company"
          />
        </div>

        <div>
          <label className="block text-xs text-text-muted mb-1">Slug</label>
          <input
            type="text"
            value={slug}
            onChange={(e) => handleSlugChange(e.target.value)}
            className="w-full bg-surface-alt border border-border rounded-md px-3 py-2 text-sm text-text font-mono placeholder:text-text-dim focus:outline-none focus:border-accent-cyan"
            placeholder="my-company"
          />
        </div>

        <div>
          <label className="block text-xs text-text-muted mb-1">Domain (optional)</label>
          <input
            type="text"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            className="w-full bg-surface-alt border border-border rounded-md px-3 py-2 text-sm text-text placeholder:text-text-dim focus:outline-none focus:border-accent-cyan"
            placeholder="company.com"
          />
        </div>

        <div>
          <label className="block text-xs text-text-muted mb-1">Admin Email (optional)</label>
          <input
            type="email"
            value={adminEmail}
            onChange={(e) => setAdminEmail(e.target.value)}
            className="w-full bg-surface-alt border border-border rounded-md px-3 py-2 text-sm text-text placeholder:text-text-dim focus:outline-none focus:border-accent-cyan"
            placeholder="admin@company.com"
          />
          <p className="text-xs text-text-dim mt-1">
            If provided, a user with admin role will be created.
          </p>
        </div>

        {error && (
          <p className="text-red-400 text-xs">{error}</p>
        )}
      </div>
    </Modal>
  )
}
