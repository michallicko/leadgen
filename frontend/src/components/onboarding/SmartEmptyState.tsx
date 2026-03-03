/**
 * Smart Empty State — context-aware empty states for pages.
 * Extends the existing EmptyState component with onboarding context
 * (e.g., "You've saved a strategy — now import contacts").
 */

import { useNavigate, useParams } from 'react-router'
import { EmptyState } from '../ui/EmptyState'
import { withRev } from '../../lib/revision'
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
        onClick: () => navigate(withRev(`/${namespace}/import`)),
      }}
    />
  )
}

/**
 * Context-aware empty state for the Campaigns page.
 * Shows different messaging depending on whether contacts exist.
 * Includes a CTA button to create the first campaign.
 */
export function CampaignsEmptyState({ onCreateClick }: { onCreateClick?: () => void }) {
  const { namespace } = useParams<{ namespace: string }>()
  const navigate = useNavigate()
  const { data: onboardingStatus } = useOnboardingStatus()
  const hasContacts = (onboardingStatus?.contact_count ?? 0) > 0

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
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M9 9l3 3 5-5" />
          <path d="M9 17h6" />
        </svg>
      }
      title={hasContacts ? 'Ready to reach out' : 'No campaigns yet'}
      description={
        hasContacts
          ? `You have ${onboardingStatus?.contact_count} contacts ready. Create your first outreach campaign to start reaching out.`
          : 'Create your first outreach campaign from qualified contacts. Import contacts first to get started.'
      }
      action={
        hasContacts
          ? {
              label: 'Create Campaign',
              onClick: () => onCreateClick?.(),
            }
          : {
              label: 'Import Contacts',
              onClick: () => navigate(withRev(`/${namespace}/import`)),
            }
      }
    />
  )
}

/**
 * Context-aware empty state for the Messages page.
 * Shows different messaging depending on whether campaigns exist.
 */
export function MessagesEmptyState() {
  const { namespace } = useParams<{ namespace: string }>()
  const navigate = useNavigate()
  const { data: onboardingStatus } = useOnboardingStatus()
  const hasCampaigns = (onboardingStatus?.campaign_count ?? 0) > 0

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
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      }
      title={hasCampaigns ? 'No messages generated yet' : 'No messages yet'}
      description={
        hasCampaigns
          ? 'Open a campaign and generate messages for your contacts. The AI will draft personalized outreach for each contact.'
          : 'Create a campaign first, then generate messages for your contacts.'
      }
      action={
        hasCampaigns
          ? {
              label: 'View Campaigns',
              onClick: () => navigate(withRev(`/${namespace}/campaigns`)),
            }
          : {
              label: 'Create Campaign',
              onClick: () => navigate(withRev(`/${namespace}/campaigns`)),
            }
      }
    />
  )
}

/**
 * Context-aware empty state for the Enrich page.
 * Shows when the namespace has no contacts to enrich.
 */
export function EnrichEmptyState() {
  const { namespace } = useParams<{ namespace: string }>()
  const navigate = useNavigate()

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
          <circle cx="11" cy="11" r="8" />
          <path d="M21 21l-4.35-4.35" />
          <path d="M11 8v6M8 11h6" />
        </svg>
      }
      title="No contacts to enrich"
      description="Import contacts first, then use the enrichment pipeline to fill in company data, verify emails, and score your prospects."
      action={{
        label: 'Import Contacts',
        onClick: () => navigate(withRev(`/${namespace}/import`)),
      }}
    />
  )
}
