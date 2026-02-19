import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../client'

interface Namespace {
  id: string
  name: string
  slug: string
  domain: string | null
  is_active: boolean
  created_at: string
}

interface NamespaceUser {
  id: string
  email: string
  display_name: string | null
  role: 'viewer' | 'editor' | 'admin' | 'super_admin'
  is_active: boolean
  created_at: string
}

interface CreateNamespaceResponse {
  tenant: Namespace
  admin_user?: { email: string; temp_password: string }
}

// Re-export types that components will need
export type { Namespace, NamespaceUser, CreateNamespaceResponse }

export function useNamespaces() {
  return useQuery({
    queryKey: ['namespaces'],
    queryFn: () => apiFetch<Namespace[]>('/tenants'),
    staleTime: 60_000,
  })
}

export function useNamespaceUsers(tenantId: string | null) {
  return useQuery({
    queryKey: ['namespace-users', tenantId],
    queryFn: () => apiFetch<NamespaceUser[]>(`/tenants/${tenantId}/users`),
    enabled: !!tenantId,
    staleTime: 30_000,
  })
}

export function useCreateNamespace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; slug: string; domain?: string; admin_email?: string }) =>
      apiFetch<CreateNamespaceResponse>('/tenants', { method: 'POST', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['namespaces'] })
    },
  })
}

export function useUpdateNamespace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      ...data
    }: {
      id: string
      name?: string
      domain?: string
      is_active?: boolean
    }) => apiFetch<Namespace>(`/tenants/${id}`, { method: 'PUT', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['namespaces'] })
    },
  })
}

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      email: string
      display_name: string
      password: string
      role: string
      tenant_id: string
    }) => apiFetch<NamespaceUser>('/users', { method: 'POST', body: data }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['namespace-users', vars.tenant_id] })
    },
  })
}

export function useUpdateUserRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      userId,
      role,
      tenantId,
    }: {
      userId: string
      role: string
      tenantId: string
    }) => apiFetch(`/users/${userId}`, { method: 'PUT', body: { role, tenant_id: tenantId } }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['namespace-users', vars.tenantId] })
    },
  })
}

export function useRemoveUserRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, tenantId }: { userId: string; tenantId: string }) =>
      apiFetch(`/users/${userId}/roles/${tenantId}`, { method: 'DELETE' }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['namespace-users', vars.tenantId] })
    },
  })
}
