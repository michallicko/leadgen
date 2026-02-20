/* eslint-disable react-refresh/only-export-components */
import { Badge } from '../components/ui/Badge'
import type { CompanyListItem } from '../api/queries/useCompanies'
import { defineColumns } from './columns'

/** All available company columns with visibility defaults. */
export const COMPANY_COLUMNS = defineColumns<CompanyListItem>([
  {
    key: 'name',
    label: 'Name',
    sortKey: 'name',
    minWidth: '140px',
    defaultVisible: true,
  },
  {
    key: 'domain',
    label: 'Domain',
    sortKey: 'domain',
    minWidth: '100px',
    defaultVisible: true,
    render: (c) =>
      c.domain ? (
        <a
          href={`https://${c.domain}`}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="text-accent-cyan hover:underline truncate block"
        >
          {c.domain}
        </a>
      ) : (
        '-'
      ),
  },
  {
    key: 'status',
    label: 'Status',
    sortKey: 'status',
    minWidth: '110px',
    shrink: false,
    defaultVisible: true,
    render: (c) => <Badge variant="status" value={c.status} />,
  },
  {
    key: 'tier',
    label: 'Tier',
    sortKey: 'tier',
    minWidth: '110px',
    shrink: false,
    defaultVisible: true,
    render: (c) => <Badge variant="tier" value={c.tier} />,
  },
  {
    key: 'company_size',
    label: 'Size',
    minWidth: '80px',
    defaultVisible: true,
  },
  {
    key: 'geo_region',
    label: 'Region',
    minWidth: '80px',
    defaultVisible: true,
  },
  {
    key: 'revenue_range',
    label: 'Revenue',
    minWidth: '80px',
    defaultVisible: true,
  },
  {
    key: 'owner_name',
    label: 'Owner',
    minWidth: '70px',
    defaultVisible: true,
  },
  {
    key: 'tag_names',
    label: 'Tags',
    minWidth: '90px',
    defaultVisible: true,
    render: (c) => {
      const names = (c as unknown as Record<string, unknown>).tag_names as
        | string[]
        | undefined
      if (!names || names.length === 0)
        return <span className="text-text-dim">-</span>
      return (
        <span className="text-xs" title={names.join(', ')}>
          {names.join(', ')}
        </span>
      )
    },
  },
  {
    key: 'triage_score',
    label: 'Score',
    sortKey: 'triage_score',
    minWidth: '55px',
    defaultVisible: true,
    render: (c) => (c.triage_score != null ? c.triage_score.toFixed(1) : '-'),
  },
  {
    key: 'contact_count',
    label: 'Contacts',
    sortKey: 'contact_count',
    minWidth: '55px',
    defaultVisible: true,
  },
  // --- Hidden by default ---
  {
    key: 'industry',
    label: 'Industry',
    minWidth: '90px',
    defaultVisible: false,
  },
  {
    key: 'hq_country',
    label: 'HQ',
    sortKey: 'hq_country',
    minWidth: '40px',
    defaultVisible: false,
  },
  {
    key: 'business_model',
    label: 'Business Model',
    minWidth: '100px',
    defaultVisible: false,
  },
  {
    key: 'ownership_type',
    label: 'Ownership',
    minWidth: '90px',
    defaultVisible: false,
  },
  {
    key: 'buying_stage',
    label: 'Buying Stage',
    minWidth: '100px',
    defaultVisible: false,
  },
  {
    key: 'engagement_status',
    label: 'Engagement',
    minWidth: '90px',
    defaultVisible: false,
  },
  {
    key: 'ai_adoption',
    label: 'AI Adoption',
    minWidth: '80px',
    defaultVisible: false,
  },
  {
    key: 'verified_employees',
    label: 'Employees',
    sortKey: 'verified_employees',
    minWidth: '70px',
    defaultVisible: false,
    render: (c) =>
      c.verified_employees != null
        ? c.verified_employees.toLocaleString()
        : '-',
  },
  {
    key: 'verified_revenue_eur_m',
    label: 'Revenue (EUR M)',
    sortKey: 'verified_revenue_eur_m',
    minWidth: '90px',
    defaultVisible: false,
    render: (c) =>
      c.verified_revenue_eur_m != null
        ? `${c.verified_revenue_eur_m.toFixed(1)}M`
        : '-',
  },
  {
    key: 'credibility_score',
    label: 'Credibility',
    sortKey: 'credibility_score',
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
    key: 'website_url',
    label: 'Website',
    minWidth: '80px',
    defaultVisible: false,
    render: (c) =>
      c.website_url ? (
        <a
          href={c.website_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="text-accent-cyan hover:underline truncate block"
        >
          Website
        </a>
      ) : (
        '-'
      ),
  },
  {
    key: 'data_quality_score',
    label: 'Data Quality',
    sortKey: 'data_quality_score',
    minWidth: '70px',
    defaultVisible: false,
  },
  {
    key: 'last_enriched_at',
    label: 'Last Enriched',
    minWidth: '100px',
    defaultVisible: false,
    render: (c) =>
      c.last_enriched_at
        ? new Date(c.last_enriched_at).toLocaleDateString()
        : '-',
  },
])

/** Column keys that cannot be hidden. */
export const COMPANY_ALWAYS_VISIBLE = ['name']
