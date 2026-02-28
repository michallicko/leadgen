/**
 * React Query hooks for strategy template CRUD and application.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'

export interface StrategyTemplate {
  id: string
  tenant_id: string | null
  name: string
  description: string | null
  category: string | null
  is_system: boolean
  metadata: Record<string, unknown>
  section_headers: string[]
  created_at: string
  updated_at: string
  content_template?: string
  extracted_data_template?: Record<string, unknown>
}

interface ApplyTemplateResponse {
  id: string
  content: string
  extracted_data: Record<string, unknown>
  version: number
  has_ai_edits: boolean
  applied_template: string
}

// ---------------------------------------------------------------------------
// List templates
// ---------------------------------------------------------------------------

export function useStrategyTemplates() {
  return useQuery({
    queryKey: ['strategy-templates'],
    queryFn: () => apiFetch<StrategyTemplate[]>('/strategy-templates'),
  })
}

// ---------------------------------------------------------------------------
// Get single template with content
// ---------------------------------------------------------------------------

export function useStrategyTemplate(templateId: string | null) {
  return useQuery({
    queryKey: ['strategy-templates', templateId],
    queryFn: () => apiFetch<StrategyTemplate>(`/strategy-templates/${templateId}`),
    enabled: !!templateId,
  })
}

// ---------------------------------------------------------------------------
// Create template from current strategy
// ---------------------------------------------------------------------------

export function useCreateStrategyTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; description?: string; category?: string }) =>
      apiFetch<StrategyTemplate>('/strategy-templates', { method: 'POST', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['strategy-templates'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Update template name/description
// ---------------------------------------------------------------------------

export function useUpdateStrategyTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { id: string; name?: string; description?: string }) => {
      const { id, ...body } = data
      return apiFetch<StrategyTemplate>(`/strategy-templates/${id}`, {
        method: 'PATCH',
        body,
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['strategy-templates'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Delete template
// ---------------------------------------------------------------------------

export function useDeleteStrategyTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/strategy-templates/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['strategy-templates'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Apply template (AI merge)
// ---------------------------------------------------------------------------

export function useApplyStrategyTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (templateId: string) =>
      apiFetch<ApplyTemplateResponse>('/playbook/apply-template', {
        method: 'POST',
        body: { template_id: templateId },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbook'] })
      qc.invalidateQueries({ queryKey: ['strategy-templates'] })
    },
  })
}
