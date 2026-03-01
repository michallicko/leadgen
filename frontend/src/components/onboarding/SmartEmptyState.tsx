/**
 * Smart Empty State — context-aware empty states for pages.
 * Extends the existing EmptyState component with onboarding context
 * (e.g., "You've saved a strategy — now import contacts").
 */

import { useNavigate, useParams } from 'react-router'
import { EmptyState } from '../ui/EmptyState'
import { useOnboardingStatus } from '../../hooks/useOnboarding'

/**
 * Context-aware empty state for the Contacts page.
 * Shows different messaging depending on whether a strategy exists.
 */
export function ContactsEmptyState() {
  const { namespace } = useParams<{ namespace: string }>()
  const navigate = useNavigate()
  const { data: status } = useOnboardingStatus()

  const hasStrategy = status?.has_strategy ?? false

  return (
    <EmptyState
      icon={
        <svg
          viewBox="0 0 24 24"
          className="w-12 h-12"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
          <circle cx="8.5" cy="7" r="4" />
          <path d="M20 8v6M23 11h-6" />
        </svg>
      }
      title={
        hasStrategy
          ? "Your strategy is ready — now find your audience"
          : 'No contacts yet'
      }
      description={
        hasStrategy
          ? "Import contacts that match the ICP you defined in your strategy. Upload a CSV or connect a data source."
          : 'Import your prospect list to start building campaigns. You can upload a CSV file or add contacts manually.'
      }
      action={{
        label: 'Import Contacts',
        onClick: () => navigate(`/${namespace}/import`),
      }}
    />
  )
}

/**
 * Context-aware empty state for the Campaigns page.
 * Shows different messaging depending on whether contacts exist.
 * No CTA button — the page header already has a "New Campaign" button.
 */
export function CampaignsEmptyState() {
  const { data: onboardingStatus } = useOnboardingStatus()
  const hasContacts = (onboardingStatus?.contact_count ?? 0) > 0

  return (
    <EmptyState
      title={hasContacts ? 'Ready to reach out' : 'No campaigns yet'}
      description={
        hasContacts
          ? `You have ${onboardingStatus?.contact_count} contacts ready. Create a campaign to start reaching out.`
          : 'Import contacts first, then create a campaign to start outreach.'
      }
    />
  )
}
