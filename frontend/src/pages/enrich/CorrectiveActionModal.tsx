/**
 * CorrectiveActionModal — shows failed/review entities for a stage+batch
 * with approve/retry/disqualify actions per entity.
 */

import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'
import { LargeModal } from '../../components/ui/LargeModal'
import { EntityResultsTable, type EntityResult } from '../../components/ui/EntityResultsTable'
import { CorrectiveActionButtons } from '../../components/ui/CorrectiveActionButtons'

interface ReviewItem {
  id: string
  name: string
  domain: string
  status: string
  flags: string[]
  enrichment_cost_usd: number
}

interface ReviewResponse {
  items: ReviewItem[]
  total: number
}

interface CorrectiveActionModalProps {
  isOpen: boolean
  onClose: () => void
  batchName: string
  stageCode: string
  stageName: string
}

export function CorrectiveActionModal({
  isOpen,
  onClose,
  batchName,
  stageCode,
  stageName,
}: CorrectiveActionModalProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['enrich-review', batchName, stageCode],
    queryFn: () =>
      apiFetch<ReviewResponse>('/enrich/review', {
        params: { batch_name: batchName, stage: stageCode },
      }),
    enabled: isOpen && !!batchName,
  })

  const results: EntityResult[] = (data?.items ?? []).map((item) => ({
    entity_id: item.id,
    entity_name: item.name,
    entity_type: 'company' as const,
    stage: stageCode,
    status: item.status,
    error: item.flags.join('; '),
    cost_usd: item.enrichment_cost_usd,
  }))

  return (
    <LargeModal
      isOpen={isOpen}
      onClose={onClose}
      title={`${stageName} — Review & Fix`}
      subtitle={`${data?.total ?? 0} entities need attention in ${batchName}`}
      isLoading={isLoading}
    >
      <EntityResultsTable
        results={results}
        emptyText="No entities need review for this stage."
        actions={(item) => (
          <CorrectiveActionButtons companyId={item.entity_id} />
        )}
      />
    </LargeModal>
  )
}
