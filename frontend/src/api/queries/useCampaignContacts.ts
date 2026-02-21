import { useInfiniteQuery } from '@tanstack/react-query'
import { apiFetch } from '../client.ts'
import type { ContactListItem } from './useContacts.ts'

/**
 * Extended contact data with enrichment readiness for the campaign picker.
 * Enrichment level is derived from the contact's scores and available data.
 */
export interface PickerContact extends ContactListItem {
  enrichment_level: 'L2' | 'L1' | 'None'
}

interface PickerContactsPage {
  contacts: PickerContact[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface PickerFilters {
  search?: string
  owner_name?: string
  tag_name?: string
  industry?: string
  company_status?: string
  enrichment_ready?: boolean
  exclude_campaign_id?: string
  sort?: string
  sort_dir?: string
}

const PAGE_SIZE = 50

/**
 * Derive enrichment level from available contact data.
 * Uses contact_score and ai_champion_score as proxies:
 * - If ai_champion_score exists, the contact went through person enrichment (L2+)
 * - If contact_score exists but no ai_champion, basic enrichment was done (L1)
 * - Otherwise no enrichment
 */
function deriveEnrichmentLevel(c: ContactListItem): 'L2' | 'L1' | 'None' {
  // ai_champion_score is set during person enrichment (requires L2 company)
  if (c.ai_champion_score != null && c.ai_champion_score > 0) return 'L2'
  // authority_score also comes from person enrichment
  if (c.authority_score != null && c.authority_score > 0) return 'L2'
  // contact_score alone suggests at least L1 processing
  if (c.contact_score != null && c.contact_score > 0) return 'L1'
  return 'None'
}

/**
 * Fetch contacts available for a campaign. Reuses the /api/contacts endpoint
 * with exclude_campaign_id to filter out already-added contacts.
 */
export function useAvailableContacts(filters: PickerFilters) {
  return useInfiniteQuery({
    queryKey: ['available-contacts', filters],
    queryFn: async ({ pageParam = 1 }) => {
      const params: Record<string, string> = {
        page: String(pageParam),
        page_size: String(PAGE_SIZE),
      }

      if (filters.search) params.search = filters.search
      if (filters.owner_name) params.owner_name = filters.owner_name
      if (filters.tag_name) params.tag_name = filters.tag_name
      if (filters.industry) params.industry = filters.industry
      if (filters.company_status) params.company_status = filters.company_status
      if (filters.exclude_campaign_id) params.exclude_campaign_id = filters.exclude_campaign_id
      if (filters.sort) params.sort = filters.sort
      if (filters.sort_dir) params.sort_dir = filters.sort_dir

      const raw = await apiFetch<{
        contacts: ContactListItem[]
        total: number
        page: number
        page_size: number
        pages: number
      }>('/contacts', { params })

      let contacts: PickerContact[] = raw.contacts.map((c) => ({
        ...c,
        enrichment_level: deriveEnrichmentLevel(c),
      }))

      // Client-side enrichment_ready toggle: only show L2-enriched contacts
      if (filters.enrichment_ready) {
        contacts = contacts.filter((c) => c.enrichment_level === 'L2')
      }

      return {
        contacts,
        total: raw.total,
        page: raw.page,
        page_size: raw.page_size,
        pages: raw.pages,
      } satisfies PickerContactsPage
    },
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pages ? lastPage.page + 1 : undefined,
    initialPageParam: 1,
  })
}
