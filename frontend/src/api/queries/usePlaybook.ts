import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'

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
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  extra: Record<string, unknown>
  created_at: string
}

interface ChatResponse {
  messages: ChatMessage[]
}

export interface ResearchStatus {
  status: 'not_started' | 'in_progress' | 'completed'
  company?: { id: string; name: string; domain: string; status: string }
  enrichment_data?: Record<string, unknown>
}

export function usePlaybookDocument() {
  return useQuery({
    queryKey: ['playbook'],
    queryFn: () => apiFetch<StrategyDocument>('/playbook'),
  })
}

export function useSavePlaybook() {
  return useMutation({
    mutationFn: (data: { content: string }) =>
      apiFetch<StrategyDocument>('/playbook', { method: 'PUT', body: data }),
  })
}

export function usePlaybookChat() {
  return useQuery({
    queryKey: ['playbook', 'chat'],
    queryFn: () => apiFetch<ChatResponse>('/playbook/chat'),
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
  return useQuery({
    queryKey: ['playbook', 'research'],
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
    mutationFn: (data: { domain: string; objective: string }) =>
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
