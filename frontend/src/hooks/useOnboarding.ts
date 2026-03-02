/**
 * Onboarding hook — fetches namespace data counts and onboarding settings.
 * Used to control signpost, smart empty states, and progress checklist.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../api/client'

export interface OnboardingStatus {
  contact_count: number
  campaign_count: number
  has_strategy: boolean
  onboarding_path: string | null
  checklist_dismissed: boolean
}

interface OnboardingSettingsPayload {
  onboarding_path?: string | null
  checklist_dismissed?: boolean
}

export function useOnboardingStatus() {
  return useQuery({
    queryKey: ['onboarding-status'],
    queryFn: () => apiFetch<OnboardingStatus>('/tenants/onboarding-status'),
    staleTime: 30_000,
  })
}

export function usePatchOnboardingSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (settings: OnboardingSettingsPayload) =>
      apiFetch('/tenants/onboarding-settings', {
        method: 'PATCH',
        body: settings,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['onboarding-status'] })
    },
  })
}

/** Derived state helpers */
export function isNamespaceEmpty(status: OnboardingStatus | undefined): boolean {
  if (!status) return false
  return !status.has_strategy && status.contact_count === 0 && status.campaign_count === 0
}

export function shouldShowSignpost(status: OnboardingStatus | undefined): boolean {
  if (!status) return false
  // Show signpost when namespace is empty and no path has been selected yet
  return isNamespaceEmpty(status) && !status.onboarding_path
}

export function shouldShowChecklist(status: OnboardingStatus | undefined): boolean {
  if (!status) return false
  // Show checklist when user has started onboarding but hasn't completed everything
  // and hasn't dismissed it
  if (status.checklist_dismissed) return false
  const allComplete =
    status.has_strategy && status.contact_count > 0 && status.campaign_count > 0
  // Don't show if everything is already done or nothing has started and no path chosen
  if (allComplete) return false
  if (isNamespaceEmpty(status) && !status.onboarding_path) return false
  return true
}
