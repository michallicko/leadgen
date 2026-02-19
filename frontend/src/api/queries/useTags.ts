import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../client'

export interface Tag {
  id: string
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

interface TagsResponse {
  tags: Tag[]
  owners: Owner[]
  custom_fields: CustomFieldDef[]
}

export function useTags() {
  return useQuery({
    queryKey: ['tags'],
    queryFn: () => apiFetch<TagsResponse>('/tags'),
    staleTime: 5 * 60_000,
  })
}
