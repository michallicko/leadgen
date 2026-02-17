import { useState, useCallback, useMemo } from 'react'
import {
  useCampaignContacts,
  useAddCampaignContacts,
  useRemoveCampaignContacts,
  type CampaignContactItem,
} from '../../../api/queries/useCampaigns'
import { useToast } from '../../../components/ui/Toast'
import { MiniTable } from '../../../components/ui/DetailField'
import { ContactPicker } from '../ContactPicker'

interface Props {
  campaignId: string
  isEditable: boolean
  onNavigate: (type: 'company' | 'contact', id: string) => void
}

export function ContactsTab({ campaignId, isEditable, onNavigate }: Props) {
  const { toast } = useToast()
  const { data: contactsData, isLoading } = useCampaignContacts(campaignId)
  const addContacts = useAddCampaignContacts()
  const removeContacts = useRemoveCampaignContacts()
  const [showPicker, setShowPicker] = useState(false)

  const contacts = useMemo(() => contactsData?.contacts ?? [], [contactsData])

  const handleAddContacts = useCallback(async (contactIds: string[]) => {
    try {
      const result = await addContacts.mutateAsync({ campaignId, contactIds })
      toast(`Added ${result.added} contact${result.added !== 1 ? 's' : ''}${result.skipped ? ` (${result.skipped} already assigned)` : ''}`, 'success')
      setShowPicker(false)
    } catch {
      toast('Failed to add contacts', 'error')
    }
  }, [campaignId, addContacts, toast])

  const handleRemoveContact = useCallback(async (contactId: string) => {
    try {
      await removeContacts.mutateAsync({ campaignId, contactIds: [contactId] })
      toast('Contact removed', 'success')
    } catch {
      toast('Failed to remove contact', 'error')
    }
  }, [campaignId, removeContacts, toast])

  const columns = useMemo(() => [
    {
      key: 'full_name' as const,
      label: 'Name',
      render: (c: CampaignContactItem) => (
        <button
          onClick={() => onNavigate('contact', c.contact_id)}
          className="text-sm text-accent-cyan hover:underline bg-transparent border-none cursor-pointer p-0 text-left"
        >
          {c.full_name || 'Unknown'}
        </button>
      ),
    },
    {
      key: 'job_title' as const,
      label: 'Title',
      render: (c: CampaignContactItem) => (
        <span className="text-xs text-text-muted">{c.job_title || '-'}</span>
      ),
    },
    {
      key: 'company_name' as const,
      label: 'Company',
      render: (c: CampaignContactItem) =>
        c.company_id ? (
          <button
            onClick={() => onNavigate('company', c.company_id!)}
            className="text-xs text-accent-cyan hover:underline bg-transparent border-none cursor-pointer p-0 text-left"
          >
            {c.company_name || '-'}
          </button>
        ) : (
          <span className="text-xs text-text-muted">-</span>
        ),
    },
    {
      key: 'status' as const,
      label: 'Status',
      render: (c: CampaignContactItem) => (
        <span className="text-xs text-text-muted">{c.status}</span>
      ),
    },
  ], [onNavigate])

  return (
    <div className="space-y-4">
      {isEditable && (
        <div className="flex gap-2">
          <button
            onClick={() => setShowPicker(true)}
            className="px-3 py-1 text-xs font-medium rounded bg-accent text-white border-none cursor-pointer hover:bg-accent-hover transition-colors"
          >
            Add Contacts
          </button>
        </div>
      )}

      {showPicker && (
        <ContactPicker
          campaignId={campaignId}
          existingContactIds={contacts.map((c) => c.contact_id)}
          onAdd={handleAddContacts}
          onClose={() => setShowPicker(false)}
          isLoading={addContacts.isPending}
        />
      )}

      {isLoading ? (
        <p className="text-xs text-text-muted">Loading contacts...</p>
      ) : contacts.length > 0 ? (
        <MiniTable
          columns={columns}
          data={contacts}
          onRowAction={isEditable ? (c) => handleRemoveContact(c.contact_id) : undefined}
          actionLabel="Remove"
        />
      ) : (
        <p className="text-xs text-text-muted">No contacts assigned yet.</p>
      )}
    </div>
  )
}
