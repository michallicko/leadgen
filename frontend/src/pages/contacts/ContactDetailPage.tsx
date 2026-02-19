import { useParams, useNavigate, useLocation } from 'react-router'
import { useContact } from '../../api/queries/useContacts'
import { EntityDetailPage } from '../../components/layout/EntityDetailPage'
import { ContactDetail } from './ContactDetail'
import { withRev } from '../../lib/revision'

export function ContactDetailPage() {
  const { namespace, contactId } = useParams<{ namespace: string; contactId: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  const origin = (location.state as { origin?: string } | null)?.origin ?? withRev(`/${namespace}/contacts`)
  const { data: contact, isLoading } = useContact(contactId ?? null)

  const handleNavigate = (type: 'company' | 'contact', id: string) => {
    const path = type === 'company'
      ? `/${namespace}/companies/${id}`
      : `/${namespace}/contacts/${id}`
    navigate(withRev(path), { state: { origin } })
  }

  return (
    <EntityDetailPage
      closeTo={withRev(`/${namespace}/contacts`)}
      title={contact?.full_name ?? 'Contact'}
      subtitle={contact?.job_title ?? undefined}
      isLoading={isLoading}
    >
      {contact && <ContactDetail contact={contact} onNavigate={handleNavigate} />}
    </EntityDetailPage>
  )
}
