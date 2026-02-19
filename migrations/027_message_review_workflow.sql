-- Migration 027: Message Review Workflow (BL-045)
-- Adds version tracking + regeneration fields to messages,
-- disqualification support to contacts.

-- Messages: version tracking for LLM feedback
ALTER TABLE messages ADD COLUMN IF NOT EXISTS original_body TEXT;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS original_subject TEXT;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS edit_reason TEXT;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS edit_reason_text TEXT;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS regen_count INTEGER DEFAULT 0;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS regen_config JSONB;

-- Contacts: disqualification support
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS is_disqualified BOOLEAN DEFAULT false;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS disqualified_at TIMESTAMPTZ;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS disqualified_reason TEXT;

-- Index for filtering non-disqualified contacts in campaign pickers
CREATE INDEX IF NOT EXISTS idx_contacts_disqualified
    ON contacts(tenant_id) WHERE is_disqualified = true;
