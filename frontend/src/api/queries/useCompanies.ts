import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'

export interface CompanyListItem {
  id: string
  name: string
  domain: string | null
  status: string | null
  enrichment_stage: string | null
  tier: string | null
  owner_name: string | null
  tag_name: string | null
  tag_names?: string[]
  industry: string | null
  hq_country: string | null
  triage_score: number | null
  score: number | null
  contact_count: number
  company_size: string | null
  geo_region: string | null
  revenue_range: string | null
  business_model: string | null
  ownership_type: string | null
  buying_stage: string | null
  engagement_status: string | null
  ai_adoption: string | null
  verified_employees: number | null
  verified_revenue_eur_m: number | null
  credibility_score: number | null
  linkedin_url: string | null
  website_url: string | null
  data_quality_score: number | null
  last_enriched_at: string | null
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
  linkedin_url: string | null
  seniority_level: string | null
  department: string | null
  ai_champion: boolean | null
  ai_champion_score: number | null
  authority_score: number | null
  person_summary: string | null
  career_trajectory: string | null
}

export interface CompanyTag {
  category: string
  value: string
}

export interface CompanyEnrichmentL1 {
  triage_notes: string | null
  pre_score: number | null
  research_query: string | null
  raw_response: Record<string, unknown> | null
  confidence: number | null
  quality_score: number | null
  qc_flags: string[] | null
  enriched_at: string | null
  enrichment_cost_usd: number | null
}

export interface L2ModuleBase {
  enriched_at: string | null
  enrichment_cost_usd: number | null
}

export interface L2Profile extends L2ModuleBase {
  company_intel: string | null
  key_products: string | null
  customer_segments: string | null
  competitors: string | null
  tech_stack: string | null
  leadership_team: string | null
  certifications: string | null
}

export interface L2Signals extends L2ModuleBase {
  digital_initiatives: string | null
  ai_adoption_level: string | null
  growth_indicators: string | null
  job_posting_count: number | null
  hiring_departments: string | null
  news_confidence: string | null
}

export interface L2Market extends L2ModuleBase {
  recent_news: string | null
  funding_history: string | null
  eu_grants: string | null
  media_sentiment: string | null
  press_releases: string | null
  thought_leadership: string | null
}

export interface L2Opportunity extends L2ModuleBase {
  pain_hypothesis: string | null
  relevant_case_study: string | null
  ai_opportunities: string | null
  quick_wins: unknown[] | null
  industry_pain_points: string | null
  cross_functional_pain: string | null
  adoption_barriers: string | null
}

export interface CompanyEnrichmentL2 {
  modules: {
    profile?: L2Profile
    signals?: L2Signals
    market?: L2Market
    opportunity?: L2Opportunity
  }
  enriched_at: string | null
  enrichment_cost_usd: number | null
}

export interface StageCompletion {
  stage: string
  status: string
  cost_usd: number | null
  completed_at: string | null
  error?: string | null
}

export interface DerivedStage {
  label: string
  stage: string | null
  color: string
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
  batch_name?: string | null
  ico: string | null
  website_url: string | null
  linkedin_url: string | null
  logo_url: string | null
  last_enriched_at: string | null
  data_quality_score: number | null
  enrichment_l1: CompanyEnrichmentL1 | null
  enrichment_l2: CompanyEnrichmentL2 | null
  registry_data: Record<string, unknown> | null
  stage_completions: StageCompletion[]
  derived_stage: DerivedStage | null
  tags: CompanyTag[]
  contacts: CompanyContactSummary[]
}

export interface CompanyFilters {
  search?: string
  tag_name?: string
  owner_name?: string
  sort?: string
  sort_dir?: string
  // Multi-value filters (comma-separated values)
  enrichment_stage?: string
  enrichment_stage_exclude?: string
  tier?: string
  tier_exclude?: string
  industry?: string
  industry_exclude?: string
  company_size?: string
  company_size_exclude?: string
  geo_region?: string
  geo_region_exclude?: string
  revenue_range?: string
  revenue_range_exclude?: string
  [key: string]: string | undefined
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
      // Pass through all non-empty filter values
      for (const [key, value] of Object.entries(filters)) {
        if (value) params[key] = value
      }
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
