-- Migration 032: Outreach campaign tables
-- Adds email send tracking, LinkedIn send queue, and campaign sender config

-- Resend email tracking
CREATE TABLE IF NOT EXISTS email_send_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    message_id UUID NOT NULL REFERENCES messages(id),
    resend_message_id TEXT,
    status VARCHAR(20) DEFAULT 'queued',
    from_email TEXT,
    to_email TEXT,
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- LinkedIn send queue for Chrome extension
CREATE TABLE IF NOT EXISTS linkedin_send_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    message_id UUID NOT NULL REFERENCES messages(id),
    contact_id UUID NOT NULL REFERENCES contacts(id),
    owner_id UUID NOT NULL REFERENCES owners(id),
    action_type VARCHAR(20) NOT NULL,
    linkedin_url TEXT,
    body TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'queued',
    claimed_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    error TEXT,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Campaign sender configuration
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS sender_config JSONB DEFAULT '{}';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_email_send_log_tenant_status ON email_send_log(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_email_send_log_message ON email_send_log(message_id);
CREATE INDEX IF NOT EXISTS idx_linkedin_queue_owner_status ON linkedin_send_queue(owner_id, status);
CREATE INDEX IF NOT EXISTS idx_linkedin_queue_tenant ON linkedin_send_queue(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_campaign_contacts_status ON campaign_contacts(campaign_id, status);
CREATE INDEX IF NOT EXISTS idx_campaign_contacts_generated ON campaign_contacts(campaign_id, generated_at);
