import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'

export interface StrategyDocument {
  id: string
  content: Record<string, unknown>
  extracted_data: Record<string, unknown>
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

export function usePlaybookDocument() {
  return useQuery({
    queryKey: ['playbook'],
    queryFn: () => apiFetch<StrategyDocument>('/playbook'),
  })
}

export function useSavePlaybook() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { content: Record<string, unknown>; version: number }) =>
      apiFetch<StrategyDocument>('/playbook', { method: 'PUT', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook'] })
    },
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
