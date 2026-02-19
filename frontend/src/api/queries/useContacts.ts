import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'

export interface ContactListItem {
  id: string
  full_name: string
  first_name: string
  last_name: string
  job_title: string | null
  company_id: string | null
  company_name: string | null
  email_address: string | null
  contact_score: number | null
  icp_fit: string | null
  message_status: string | null
  owner_name: string | null
  tag_name: string | null
}

interface ContactsPage {
  contacts: ContactListItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface ContactMessage {
  id: string
  channel: string | null
  sequence_step: number | null
  variant: string | null
  subject: string | null
  status: string | null
  tone: string | null
}

export interface ContactEnrichment {
  person_summary: string | null
  linkedin_profile_summary: string | null
  relationship_synthesis: string | null
  ai_champion: boolean | null
  ai_champion_score: number | null
  authority_score: number | null
  career_trajectory: string | null
  previous_companies: Array<Record<string, unknown>> | null
  speaking_engagements: string | null
  publications: string | null
  twitter_handle: string | null
  github_username: string | null
  enriched_at: string | null
  enrichment_cost_usd: number | null
}

export interface StageCompletion {
  stage: string
  status: string
  completed_at: string | null
  cost_usd: number | null
  error: string | null
}

export interface ContactDetail {
  id: string
  first_name: string
  last_name: string
  full_name: string
  job_title: string | null
  email_address: string | null
  linkedin_url: string | null
  phone_number: string | null
  profile_photo_url: string | null
  seniority_level: string | null
  department: string | null
  location_city: string | null
  location_country: string | null
  icp_fit: string | null
  relationship_status: string | null
  contact_source: string | null
  language: string | null
  message_status: string | null
  ai_champion: string | null
  ai_champion_score: number | null
  authority_score: number | null
  contact_score: number | null
  enrichment_cost_usd: number | null
  processed_enrich: boolean | null
  email_lookup: string | null
  duplicity_check: string | null
  duplicity_conflict: string | null
  duplicity_detail: string | null
  notes: string | null
  error: string | null
  custom_fields: Record<string, string>
  created_at: string | null
  updated_at: string | null
  last_enriched_at: string | null
  employment_status: string | null
  employment_verified_at: string | null
  company: {
    id: string
    name: string
    domain: string | null
    status: string | null
    tier: string | null
  } | null
  owner_name: string | null
  tag_name: string | null
  batch_name?: string | null
  enrichment: ContactEnrichment | null
  stage_completions: StageCompletion[]
  messages: ContactMessage[]
  batch_name?: string | null
  stage_completions?: { stage: string; status: string; cost_usd: number | null; completed_at: string | null; error?: string | null }[]
}

export interface ContactFilters {
  search?: string
  tag_name?: string
  owner_name?: string
  icp_fit?: string
  message_status?: string
  sort?: string
  sort_dir?: string
}

const PAGE_SIZE = 50

export function useContacts(filters: ContactFilters) {
  return useInfiniteQuery({
    queryKey: ['contacts', filters],
    queryFn: ({ pageParam = 1 }) => {
      const params: Record<string, string> = {
        page: String(pageParam),
        page_size: String(PAGE_SIZE),
      }
      if (filters.search) params.search = filters.search
      if (filters.tag_name) params.tag_name = filters.tag_name
      if (filters.owner_name) params.owner_name = filters.owner_name
      if (filters.icp_fit) params.icp_fit = filters.icp_fit
      if (filters.message_status) params.message_status = filters.message_status
      if (filters.sort) params.sort = filters.sort
      if (filters.sort_dir) params.sort_dir = filters.sort_dir
      return apiFetch<ContactsPage>('/contacts', { params })
    },
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pages ? lastPage.page + 1 : undefined,
    initialPageParam: 1,
  })
}

export function useContact(id: string | null) {
  return useQuery({
    queryKey: ['contact', id],
    queryFn: () => apiFetch<ContactDetail>(`/contacts/${id}`),
    enabled: !!id,
  })
}

export function useUpdateContact() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      apiFetch(`/contacts/${id}`, { method: 'PATCH', body: data }),
    onSuccess: (_data, { id }) => {
      qc.invalidateQueries({ queryKey: ['contact', id] })
      qc.invalidateQueries({ queryKey: ['contacts'] })
    },
  })
}
