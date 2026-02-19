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

export function useFilterCounts(payload: {
  filters: Record<string, { values: string[]; exclude: boolean }>
  search?: string
  tag_name?: string
  owner_name?: string
}) {
  return useQuery<FilterCountsResponse>({
    queryKey: ['contact-filter-counts', payload],
    queryFn: () => apiFetch<FilterCountsResponse>('/contacts/filter-counts', {
      method: 'POST',
      body: payload,
    }),
    staleTime: 10_000,
    refetchOnWindowFocus: false,
  })
}
