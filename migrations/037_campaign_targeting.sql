-- Migration 037: Campaign targeting columns + overlap audit log
-- BL-052: Contact Search API + Chat Tools (Phase 1)

-- Add strategy linking and targeting metadata to campaigns
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS strategy_id UUID REFERENCES strategy_documents(id);
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS target_criteria JSONB DEFAULT '{}'::jsonb;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS conflict_report JSONB DEFAULT '{}'::jsonb;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS contact_cooldown_days INT DEFAULT 30;

-- Overlap audit log
CREATE TABLE IF NOT EXISTS campaign_overlap_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    contact_id UUID NOT NULL REFERENCES contacts(id),
    campaign_id UUID NOT NULL REFERENCES campaigns(id),
    overlapping_campaign_id UUID NOT NULL REFERENCES campaigns(id),
    overlap_type TEXT NOT NULL,
    resolved BOOLEAN DEFAULT false,
    resolved_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_campaign_overlap_tenant ON campaign_overlap_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_campaign_overlap_contact ON campaign_overlap_log(contact_id);
