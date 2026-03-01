import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'

export interface PlaybookContact {
  id: string
  first_name: string
  last_name: string
  full_name: string
  job_title: string | null
  company_id: string | null
  company_name: string | null
  email_address: string | null
  seniority_level: string | null
  contact_score: number | null
  icp_fit: string | null
  industry: string | null
  company_size: string | null
  company_status: string | null
}

export interface PlaybookContactsFilters {
  industries?: string[]
  seniority_levels?: string[]
  geo_regions?: string[]
  company_sizes?: string[]
}

interface PlaybookContactsResponse {
  filters: { applied_filters: PlaybookContactsFilters }
  contacts: PlaybookContact[]
  total: number
  page: number
  per_page: number
  pages: number
  icp_source: boolean
}

interface ConfirmSelectionResponse {
  success: boolean
  selected_count: number
  phase: string
  playbook_selections: Record<string, unknown>
}

/**
 * Fetch contacts filtered by the playbook's ICP criteria.
 * Supports filter overrides, search, pagination, and sort.
 */
export function usePlaybookContacts(
  filters: PlaybookContactsFilters = {},
  options: {
    page?: number
    per_page?: number
    sort?: string
    sort_dir?: 'asc' | 'desc'
    search?: string
    enabled?: boolean
  } = {},
) {
  const {
    page = 1,
    per_page = 25,
    sort = 'last_name',
    sort_dir = 'asc',
    search = '',
    enabled = true,
  } = options

  // Build query params from filters
  const params: Record<string, string> = {
    page: String(page),
    per_page: String(per_page),
    sort,
    sort_dir,
  }

  if (search) params.search = search
  if (filters.industries?.length) params.industries = filters.industries.join(',')
  if (filters.seniority_levels?.length) params.seniority_levels = filters.seniority_levels.join(',')
  if (filters.geo_regions?.length) params.geo_regions = filters.geo_regions.join(',')
  if (filters.company_sizes?.length) params.company_sizes = filters.company_sizes.join(',')

  return useQuery({
    queryKey: ['playbook', 'contacts', params],
    queryFn: () =>
      apiFetch<PlaybookContactsResponse>('/playbook/contacts', { params }),
    enabled,
  })
}

/**
 * Confirm contact selection and advance playbook phase to messages.
 */
export function useConfirmContactSelection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (selectedIds: string[]) =>
      apiFetch<ConfirmSelectionResponse>('/playbook/contacts/confirm', {
        method: 'POST',
        body: { selected_ids: selectedIds },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook'] })
    },
  })
}
