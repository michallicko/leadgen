import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../client'

interface Batch {
  name: string
}

interface Owner {
  id: string
  name: string
}

interface CustomFieldDef {
  id: string
  entity_type: string
  field_key: string
  display_name: string
  field_type: string
  options: string[] | null
  display_order: number
}

interface BatchesResponse {
  batches: Batch[]
  owners: Owner[]
  custom_fields: CustomFieldDef[]
}

export function useBatches() {
  return useQuery({
    queryKey: ['batches'],
    queryFn: () => apiFetch<BatchesResponse>('/batches'),
    staleTime: 5 * 60_000,
  })
}
