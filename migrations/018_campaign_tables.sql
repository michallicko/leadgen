-- 018: Extend campaigns table + campaign_contacts + campaign_templates
-- BL-031: Campaign CRUD + Data Model

BEGIN;

-- ── Extend campaigns table ───────────────────────────────────

ALTER TABLE campaigns
  ADD COLUMN IF NOT EXISTS status          TEXT DEFAULT 'draft',
  ADD COLUMN IF NOT EXISTS description     TEXT,
  ADD COLUMN IF NOT EXISTS template_config JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS generation_config JSONB DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS total_contacts  INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS generated_count INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS generation_cost NUMERIC(10,4) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS generation_started_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS generation_completed_at TIMESTAMPTZ;

-- ── Campaign contacts junction ───────────────────────────────

CREATE TABLE IF NOT EXISTS campaign_contacts (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id     UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  contact_id      UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  tenant_id       UUID NOT NULL REFERENCES tenants(id),
  status          TEXT DEFAULT 'pending',
  enrichment_gaps JSONB DEFAULT '[]'::jsonb,
  generation_cost NUMERIC(10,4) DEFAULT 0,
  error           TEXT,
  added_at        TIMESTAMPTZ DEFAULT now(),
  generated_at    TIMESTAMPTZ,
  UNIQUE(campaign_id, contact_id)
);

CREATE INDEX IF NOT EXISTS idx_campaign_contacts_campaign ON campaign_contacts(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_contacts_contact ON campaign_contacts(contact_id);
CREATE INDEX IF NOT EXISTS idx_campaign_contacts_tenant ON campaign_contacts(tenant_id);

-- ── Campaign templates ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS campaign_templates (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id       UUID REFERENCES tenants(id),
  name            TEXT NOT NULL,
  description     TEXT,
  steps           JSONB DEFAULT '[]'::jsonb,
  default_config  JSONB DEFAULT '{}'::jsonb,
  is_system       BOOLEAN DEFAULT false,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_campaign_templates_tenant ON campaign_templates(tenant_id);

-- ── Extend messages with campaign_contact link ───────────────

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS campaign_contact_id UUID REFERENCES campaign_contacts(id);

CREATE INDEX IF NOT EXISTS idx_messages_campaign_contact ON messages(campaign_contact_id);

-- ── Seed system templates ────────────────────────────────────

INSERT INTO campaign_templates (id, tenant_id, name, description, steps, default_config, is_system) VALUES
(
  'a0000000-0000-0000-0000-000000000001',
  NULL,
  'LinkedIn + Email Sequence',
  'Full 5-step outreach: LinkedIn invite, 3 emails, and LinkedIn followup with PDF.',
  '[
    {"step": 1, "channel": "linkedin_connect", "label": "LinkedIn Invite", "enabled": true, "needs_pdf": false, "variant_count": 1},
    {"step": 2, "channel": "email", "label": "Email 1", "enabled": true, "needs_pdf": false, "variant_count": 1},
    {"step": 3, "channel": "email", "label": "Email 2", "enabled": true, "needs_pdf": false, "variant_count": 1},
    {"step": 4, "channel": "linkedin_message", "label": "LI Followup + PDF", "enabled": true, "needs_pdf": true, "variant_count": 1},
    {"step": 5, "channel": "email", "label": "Email 3", "enabled": false, "needs_pdf": false, "variant_count": 1}
  ]'::jsonb,
  '{"tone": "professional", "language": "en"}'::jsonb,
  true
),
(
  'a0000000-0000-0000-0000-000000000002',
  NULL,
  'Email 3-Step',
  'Email-only sequence: 3 emails with increasing urgency.',
  '[
    {"step": 1, "channel": "email", "label": "Email 1 - Intro", "enabled": true, "needs_pdf": false, "variant_count": 1},
    {"step": 2, "channel": "email", "label": "Email 2 - Value", "enabled": true, "needs_pdf": false, "variant_count": 1},
    {"step": 3, "channel": "email", "label": "Email 3 - Close", "enabled": true, "needs_pdf": false, "variant_count": 1}
  ]'::jsonb,
  '{"tone": "professional", "language": "en"}'::jsonb,
  true
),
(
  'a0000000-0000-0000-0000-000000000003',
  NULL,
  'LinkedIn Only',
  'LinkedIn-only: connection request + one followup message.',
  '[
    {"step": 1, "channel": "linkedin_connect", "label": "LinkedIn Invite", "enabled": true, "needs_pdf": false, "variant_count": 1},
    {"step": 2, "channel": "linkedin_message", "label": "LinkedIn Followup", "enabled": true, "needs_pdf": false, "variant_count": 1}
  ]'::jsonb,
  '{"tone": "casual", "language": "en"}'::jsonb,
  true
)
ON CONFLICT DO NOTHING;

COMMIT;
