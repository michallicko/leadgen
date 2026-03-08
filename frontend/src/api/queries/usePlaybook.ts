import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useLocation } from 'react-router'
import { useMemo } from 'react'
import { apiFetch } from '../client'
import { getNamespaceFromPath } from '../../lib/auth'

/** Return current namespace slug, re-computed when the URL changes. */
function useNamespace(): string {
  const location = useLocation()
  return useMemo(() => getNamespaceFromPath(location.pathname) ?? '', [location.pathname])
}

export interface StrategyDocument {
  id: string
  content: string | null
  objective: string | null
  enrichment_id: string | null
  extracted_data: Record<string, unknown>
  playbook_selections: Record<string, unknown>
  phase: string
  status: string
  version: number
  has_ai_edits: boolean
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  extra: Record<string, unknown>
  created_at: string
  page_context?: string | null
  thread_start?: boolean
}

interface ChatResponse {
  messages: ChatMessage[]
}

export interface ResearchStatus {
  status: 'not_started' | 'in_progress' | 'completed' | 'failed'
  company?: { id: string; name: string; domain: string; status: string }
  enrichment_data?: Record<string, unknown>
}

export function usePlaybookDocument() {
  const ns = useNamespace()
  return useQuery({
    queryKey: ['playbook', ns],
    queryFn: () => apiFetch<StrategyDocument>('/playbook'),
  })
}

export function useSavePlaybook() {
  return useMutation({
    mutationFn: (data: { content?: string; objective?: string }) =>
      apiFetch<StrategyDocument>('/playbook', { method: 'PUT', body: data }),
  })
}

export function usePlaybookChat(enabled = true) {
  const ns = useNamespace()
  return useQuery({
    queryKey: ['playbook', 'chat', ns],
    queryFn: () => apiFetch<ChatResponse>('/playbook/chat'),
    enabled,
  })
}

export function useSendChatMessage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { message: string }) =>
      apiFetch<ChatMessage>('/playbook/chat', { method: 'POST', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook', 'chat'] })
    },
  })
}

export function useNewThread() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiFetch<{ thread_id: string; created_at: string }>('/playbook/chat/new-thread', {
        method: 'POST',
        body: {},
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook', 'chat'] })
    },
  })
}

export function useExtractStrategy() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiFetch<Record<string, unknown>>('/playbook/extract', { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook'] })
    },
  })
}

export function useResearchStatus(enabled: boolean) {
  const ns = useNamespace()
  return useQuery({
    queryKey: ['playbook', 'research', ns],
    queryFn: () => apiFetch<ResearchStatus>('/playbook/research'),
    enabled,
    refetchInterval: (query) => {
      const data = query.state.data
      if (data && data.status === 'in_progress') return 10_000
      return false
    },
  })
}

export function useTriggerResearch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { domains: string[]; primary_domain: string; objective?: string; challenge_type?: string }) =>
      apiFetch<ResearchStatus>('/playbook/research', { method: 'POST', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook', 'research'] })
    },
  })
}

export function useAdvancePhase() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { phase: string }) =>
      apiFetch<StrategyDocument>('/playbook/phase', { method: 'PUT', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook'] })
    },
  })
}

interface UndoResponse {
  success: boolean
  restored_version: number
  current_version: number
  error?: string
}

export function useUndoAIEdit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiFetch<UndoResponse>('/playbook/undo', { method: 'POST', body: {} }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Version history (BL-1014)
// ---------------------------------------------------------------------------

export interface PlaybookVersion {
  id: string
  document_id: string
  version_number: number
  author_type: 'user' | 'ai'
  description: string
  created_at: string
  metadata: Record<string, unknown>
  content?: string
  extracted_data?: Record<string, unknown>
}

export function usePlaybookVersions(documentId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ['playbook', 'versions', documentId],
    queryFn: () => apiFetch<PlaybookVersion[]>(`/playbook/${documentId}/versions`),
    enabled: enabled && !!documentId,
  })
}

export function usePlaybookVersionDetail(documentId: string, versionId: string | null) {
  return useQuery({
    queryKey: ['playbook', 'versions', documentId, versionId],
    queryFn: () => apiFetch<PlaybookVersion>(`/playbook/${documentId}/versions/${versionId}`),
    enabled: !!versionId,
  })
}

export function useRestoreVersion(documentId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (versionId: string) =>
      apiFetch<UndoResponse>(`/playbook/${documentId}/versions/${versionId}/restore`, {
        method: 'POST',
        body: {},
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook'] })
    },
  })
}

export function useCreateVersion(documentId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { content: string; description?: string }) =>
      apiFetch<PlaybookVersion>(`/playbook/${documentId}/versions`, {
        method: 'POST',
        body: data,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook', 'versions'] })
    },
  })
}
