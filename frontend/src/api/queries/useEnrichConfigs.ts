import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'

export interface EnrichConfigData {
  id: string
  name: string
  description: string
  config: Record<string, unknown>
  is_default: boolean
  created_at: string | null
  updated_at: string | null
}

export interface EnrichScheduleData {
  id: string
  config_id: string
  schedule_type: 'cron' | 'on_new_entity'
  cron_expression: string | null
  tag_filter: string | null
  is_active: boolean
  last_run_at: string | null
  next_run_at: string | null
  created_at: string | null
}

export function useEnrichConfigs() {
  return useQuery({
    queryKey: ['enrichment-configs'],
    queryFn: () => apiFetch<EnrichConfigData[]>('/enrichment-configs'),
    staleTime: 30_000,
  })
}

export function useSaveConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; description?: string; config: Record<string, unknown>; is_default?: boolean }) =>
      apiFetch<EnrichConfigData>('/enrichment-configs', { method: 'POST', body: data }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['enrichment-configs'] }),
  })
}

export function useUpdateConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string; name?: string; config?: Record<string, unknown>; is_default?: boolean }) =>
      apiFetch<EnrichConfigData>(`/enrichment-configs/${id}`, { method: 'PATCH', body: data }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['enrichment-configs'] }),
  })
}

export function useDeleteConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/enrichment-configs/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['enrichment-configs'] }),
  })
}

export function useEnrichSchedules() {
  return useQuery({
    queryKey: ['enrichment-schedules'],
    queryFn: () => apiFetch<EnrichScheduleData[]>('/enrichment-schedules'),
    staleTime: 30_000,
  })
}

export function useSaveSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { config_id: string; schedule_type: string; cron_expression?: string; tag_filter?: string }) =>
      apiFetch<EnrichScheduleData>('/enrichment-schedules', { method: 'POST', body: data }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['enrichment-schedules'] }),
  })
}

export function useDeleteSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/enrichment-schedules/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['enrichment-schedules'] }),
  })
}

export function useToggleSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      apiFetch<EnrichScheduleData>(`/enrichment-schedules/${id}`, { method: 'PATCH', body: { is_active } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['enrichment-schedules'] }),
  })
}
