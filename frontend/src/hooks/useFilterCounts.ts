import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'

interface FacetEntry {
  value: string
  count: number
}

export interface FilterCountsResponse {
  total: number
  facets: Record<string, FacetEntry[]>
}

interface FilterCountsPayload {
  filters: Record<string, { values: string[]; exclude: boolean }>
  search?: string
  tag_name?: string
  owner_name?: string
}

/**
 * Generic filter-counts hook. Endpoint defaults to contacts.
 * Pass endpoint='/companies/filter-counts' for companies.
 */
export function useFilterCounts(
  payload: FilterCountsPayload,
  endpoint: string = '/contacts/filter-counts',
) {
  return useQuery<FilterCountsResponse>({
    queryKey: ['filter-counts', endpoint, payload],
    queryFn: () => apiFetch<FilterCountsResponse>(endpoint, {
      method: 'POST',
      body: payload,
    }),
    staleTime: 10_000,
    refetchOnWindowFocus: false,
  })
}
