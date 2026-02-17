import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'

export interface CompanyListItem {
  id: string
  name: string
  domain: string | null
  status: string | null
  tier: string | null
  owner_name: string | null
  tag_name: string | null
  industry: string | null
  hq_country: string | null
  triage_score: number | null
  contact_count: number
}

interface CompaniesPage {
  companies: CompanyListItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface CompanyContactSummary {
  id: string
  full_name: string
  first_name: string | null
  last_name: string | null
  job_title: string | null
  email_address: string | null
  contact_score: number | null
  icp_fit: string | null
  message_status: string | null
}

export interface CompanyTag {
  category: string
  value: string
}

export interface CompanyDetail {
  id: string
  name: string
  domain: string | null
  status: string | null
  tier: string | null
  business_model: string | null
  company_size: string | null
  ownership_type: string | null
  geo_region: string | null
  industry: string | null
  industry_category: string | null
  revenue_range: string | null
  buying_stage: string | null
  engagement_status: string | null
  crm_status: string | null
  ai_adoption: string | null
  news_confidence: string | null
  business_type: string | null
  cohort: string | null
  summary: string | null
  hq_city: string | null
  hq_country: string | null
  triage_notes: string | null
  triage_score: number | null
  verified_revenue_eur_m: number | null
  verified_employees: number | null
  enrichment_cost_usd: number | null
  pre_score: number | null
  lemlist_synced: boolean | null
  error_message: string | null
  notes: string | null
  custom_fields: Record<string, string>
  created_at: string | null
  updated_at: string | null
  owner_name: string | null
  tag_name: string | null
  ico: string | null
  enrichment_l2: Record<string, unknown> | null
  registry_data: Record<string, unknown> | null
  tags: CompanyTag[]
  contacts: CompanyContactSummary[]
}

export interface CompanyFilters {
  search?: string
  status?: string
  tier?: string
  tag_name?: string
  owner_name?: string
  sort?: string
  sort_dir?: string
}

const PAGE_SIZE = 50

export function useCompanies(filters: CompanyFilters) {
  return useInfiniteQuery({
    queryKey: ['companies', filters],
    queryFn: ({ pageParam = 1 }) => {
      const params: Record<string, string> = {
        page: String(pageParam),
        page_size: String(PAGE_SIZE),
      }
      if (filters.search) params.search = filters.search
      if (filters.status) params.status = filters.status
      if (filters.tier) params.tier = filters.tier
      if (filters.tag_name) params.tag_name = filters.tag_name
      if (filters.owner_name) params.owner_name = filters.owner_name
      if (filters.sort) params.sort = filters.sort
      if (filters.sort_dir) params.sort_dir = filters.sort_dir
      return apiFetch<CompaniesPage>('/companies', { params })
    },
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pages ? lastPage.page + 1 : undefined,
    initialPageParam: 1,
  })
}

export function useCompany(id: string | null) {
  return useQuery({
    queryKey: ['company', id],
    queryFn: () => apiFetch<CompanyDetail>(`/companies/${id}`),
    enabled: !!id,
  })
}

export function useUpdateCompany() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      apiFetch(`/companies/${id}`, { method: 'PATCH', body: data }),
    onSuccess: (_data, { id }) => {
      qc.invalidateQueries({ queryKey: ['company', id] })
      qc.invalidateQueries({ queryKey: ['companies'] })
    },
  })
}
