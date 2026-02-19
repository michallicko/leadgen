import { useParams, useNavigate, useLocation } from 'react-router'
import { useCompany } from '../../api/queries/useCompanies'
import { EntityDetailPage } from '../../components/layout/EntityDetailPage'
import { CompanyDetail } from './CompanyDetail'
import { withRev } from '../../lib/revision'

export function CompanyDetailPage() {
  const { namespace, companyId } = useParams<{ namespace: string; companyId: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  const origin = (location.state as { origin?: string } | null)?.origin ?? withRev(`/${namespace}/companies`)
  const { data: company, isLoading } = useCompany(companyId ?? null)

  const handleNavigate = (type: 'company' | 'contact', id: string) => {
    const path = type === 'company'
      ? `/${namespace}/companies/${id}`
      : `/${namespace}/contacts/${id}`
    navigate(withRev(path), { state: { origin } })
  }

  return (
    <EntityDetailPage
      closeTo={withRev(`/${namespace}/companies`)}
      title={company?.name ?? 'Company'}
      subtitle={company?.domain ?? undefined}
      isLoading={isLoading}
    >
      {company && <CompanyDetail company={company} onNavigate={handleNavigate} />}
    </EntityDetailPage>
  )
}
