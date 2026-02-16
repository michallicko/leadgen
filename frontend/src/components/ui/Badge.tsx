/**
 * Status/tier/ICP/message-status badges with color mapping.
 * Colors ported from dashboard CSS.
 */

const STATUS_COLORS: Record<string, string> = {
  'New': 'bg-[#00B8CF]/15 text-[#00B8CF] border-[#00B8CF]/30',
  'Triage: Passed': 'bg-success/15 text-success border-success/30',
  'Triage: Review': 'bg-warning/15 text-warning border-warning/30',
  'Triage: Disqualified': 'bg-error/15 text-error border-error/30',
  'Enriched L2': 'bg-[#2ecc71]/15 text-[#2ecc71] border-[#2ecc71]/30',
  'Enrichment Failed': 'bg-error/15 text-error border-error/30',
  'Enrichment L2 Failed': 'bg-error/15 text-error border-error/30',
  'Synced': 'bg-success/15 text-success border-success/30',
  'Needs Review': 'bg-warning/15 text-warning border-warning/30',
  'Enriched': 'bg-[#2ecc71]/15 text-[#2ecc71] border-[#2ecc71]/30',
  'Error pushing to Lemlist': 'bg-error/15 text-error border-error/30',
}

const TIER_COLORS: Record<string, string> = {
  'Tier 1 - Platinum': 'bg-[#e6c432]/15 text-[#e6c432] border-[#e6c432]/30',
  'Tier 2 - Gold': 'bg-[#c0c0c0]/15 text-[#c0c0c0] border-[#c0c0c0]/30',
  'Tier 3 - Silver': 'bg-[#cd7f32]/15 text-[#cd7f32] border-[#cd7f32]/30',
  'Tier 4 - Bronze': 'bg-[#a07838]/15 text-[#a07838] border-[#a07838]/30',
  'Tier 5 - Copper': 'bg-[#8a6030]/15 text-[#8a6030] border-[#8a6030]/30',
  'Deprioritize': 'bg-[#8B92A0]/10 text-text-dim border-[#8B92A0]/20',
}

const ICP_COLORS: Record<string, string> = {
  'Strong Fit': 'bg-success/15 text-success border-success/30',
  'Moderate Fit': 'bg-warning/15 text-warning border-warning/30',
  'Weak Fit': 'bg-error/15 text-error border-error/30',
  'Unknown': 'bg-[#8B92A0]/10 text-text-muted border-[#8B92A0]/20',
}

const MSG_STATUS_COLORS: Record<string, string> = {
  'approved': 'bg-success/15 text-success border-success/30',
  'pending_review': 'bg-warning/15 text-warning border-warning/30',
  'sent': 'bg-[#00B8CF]/15 text-[#00B8CF] border-[#00B8CF]/30',
  'replied': 'bg-[#2ecc71]/15 text-[#2ecc71] border-[#2ecc71]/30',
  'not_started': 'bg-[#8B92A0]/10 text-text-muted border-[#8B92A0]/20',
  'generating': 'bg-accent/15 text-accent-hover border-accent/30',
  'no_channel': 'bg-[#8B92A0]/10 text-text-muted border-[#8B92A0]/20',
  'generation_failed': 'bg-error/15 text-error border-error/30',
}

const VARIANT_MAPS: Record<string, Record<string, string>> = {
  status: STATUS_COLORS,
  tier: TIER_COLORS,
  icp: ICP_COLORS,
  msgStatus: MSG_STATUS_COLORS,
}

const DEFAULT_STYLE = 'bg-[#8B92A0]/10 text-text-muted border-[#8B92A0]/20'

interface BadgeProps {
  variant: 'status' | 'tier' | 'icp' | 'msgStatus'
  value: string | null | undefined
  className?: string
}

export function Badge({ variant, value, className = '' }: BadgeProps) {
  if (!value) return null
  const map = VARIANT_MAPS[variant]
  const colors = map[value] ?? DEFAULT_STYLE

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border whitespace-nowrap ${colors} ${className}`}
    >
      {value}
    </span>
  )
}
