/* eslint-disable react-refresh/only-export-components */
import { Badge } from '../components/ui/Badge'
import type { ContactListItem } from '../api/queries/useContacts'
import { defineColumns } from './columns'
import { renderTagBadges } from './tagBadges'

/** All available contact columns with visibility defaults. */
export const CONTACT_COLUMNS = defineColumns<ContactListItem>([
  {
    key: 'full_name',
    label: 'Name',
    sortKey: 'last_name',
    minWidth: '130px',
    defaultVisible: true,
  },
  {
    key: 'job_title',
    label: 'Title',
    sortKey: 'job_title',
    minWidth: '120px',
    defaultVisible: true,
  },
  {
    key: 'company_name',
    label: 'Company',
    minWidth: '120px',
    defaultVisible: true,
  },
  {
    key: 'email_address',
    label: 'Email',
    sortKey: 'email_address',
    minWidth: '140px',
    defaultVisible: true,
    render: (c) =>
      c.email_address ? (
        <a
          href={`mailto:${c.email_address}`}
          onClick={(e) => e.stopPropagation()}
          className="text-accent-cyan hover:underline truncate block"
        >
          {c.email_address}
        </a>
      ) : (
        '-'
      ),
  },
  {
    key: 'seniority_level',
    label: 'Seniority',
    sortKey: 'seniority_level',
    minWidth: '90px',
    defaultVisible: true,
  },
  {
    key: 'icp_fit',
    label: 'ICP Fit',
    sortKey: 'icp_fit',
    minWidth: '100px',
    shrink: false,
    defaultVisible: true,
    render: (c) => <Badge variant="icp" value={c.icp_fit} />,
  },
  {
    key: 'score',
    label: 'Score',
    sortKey: 'contact_score',
    minWidth: '55px',
    defaultVisible: true,
    render: (c) => {
      if (c.score == null) return <span className="text-text-dim">-</span>
      const val = Math.round(c.score)
      return (
        <span className="inline-flex items-center gap-1.5 text-xs tabular-nums">
          <span className="w-8 h-1.5 rounded-full bg-surface-alt overflow-hidden">
            <span
              className="block h-full rounded-full bg-accent-cyan"
              style={{ width: `${Math.min(val, 100)}%` }}
            />
          </span>
          {val}
        </span>
      )
    },
  },
  {
    key: 'message_status',
    label: 'Msg Status',
    sortKey: 'message_status',
    minWidth: '100px',
    shrink: false,
    defaultVisible: true,
    render: (c) => <Badge variant="msgStatus" value={c.message_status} />,
  },
  {
    key: 'owner_name',
    label: 'Owner',
    minWidth: '70px',
    defaultVisible: true,
  },
  // --- Hidden by default ---
  {
    key: 'contact_score',
    label: 'Contact Score',
    sortKey: 'contact_score',
    minWidth: '55px',
    defaultVisible: false,
  },
  {
    key: 'tag_names',
    label: 'Tags',
    minWidth: '90px',
    defaultVisible: false,
    render: (c) => renderTagBadges((c as unknown as Record<string, unknown>).tag_names as string[] | undefined),
  },
  {
    key: 'department',
    label: 'Department',
    sortKey: 'department',
    minWidth: '90px',
    defaultVisible: false,
  },
  {
    key: 'location_city',
    label: 'City',
    minWidth: '80px',
    defaultVisible: false,
  },
  {
    key: 'location_country',
    label: 'Country',
    minWidth: '70px',
    defaultVisible: false,
  },
  {
    key: 'linkedin_url',
    label: 'LinkedIn',
    minWidth: '80px',
    defaultVisible: false,
    render: (c) =>
      c.linkedin_url ? (
        <a
          href={c.linkedin_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="text-accent-cyan hover:underline truncate block"
        >
          LinkedIn
        </a>
      ) : (
        '-'
      ),
  },
  {
    key: 'phone_number',
    label: 'Phone',
    minWidth: '100px',
    defaultVisible: false,
  },
  {
    key: 'ai_champion_score',
    label: 'AI Champion',
    sortKey: 'ai_champion_score',
    minWidth: '70px',
    defaultVisible: false,
  },
  {
    key: 'authority_score',
    label: 'Authority',
    sortKey: 'authority_score',
    minWidth: '65px',
    defaultVisible: false,
  },
  {
    key: 'linkedin_activity_level',
    label: 'LinkedIn Activity',
    sortKey: 'linkedin_activity_level',
    minWidth: '100px',
    defaultVisible: false,
  },
  {
    key: 'language',
    label: 'Language',
    minWidth: '70px',
    defaultVisible: false,
  },
  {
    key: 'contact_source',
    label: 'Source',
    minWidth: '70px',
    defaultVisible: false,
  },
])

/** Column keys that cannot be hidden. */
export const CONTACT_ALWAYS_VISIBLE = ['full_name']
