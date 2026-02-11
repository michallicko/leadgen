-- ============================================================
-- Leadgen Pipeline - PostgreSQL Schema v1.0
-- Migration: Airtable → PostgreSQL
--
-- Tables: 16 (+ 3 junction tables)
-- Enums: ~30 types
-- Multi-tenant: shared schema with tenant_id
--
-- Run: psql -d leadgen -f 001_initial_schema.sql
-- ============================================================

-- ============================================================
-- LEADGEN PIPELINE - PostgreSQL Schema v1.0
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ── ENUMS ────────────────────────────────────────────────────

CREATE TYPE company_status AS ENUM (
  'new', 'enrichment_failed', 'triage_passed', 'triage_review',
  'triage_disqualified', 'enrichment_l2_failed', 'enriched_l2',
  'synced', 'needs_review', 'enriched', 'error_pushing_lemlist'
);

CREATE TYPE company_tier AS ENUM (
  'tier_1_platinum', 'tier_2_gold', 'tier_3_silver',
  'tier_4_bronze', 'tier_5_copper', 'deprioritize'
);

CREATE TYPE business_model AS ENUM (
  'b2b', 'b2c', 'marketplace', 'gov', 'non_profit', 'hybrid'
);

CREATE TYPE company_size AS ENUM (
  'micro', 'startup', 'smb', 'mid_market', 'enterprise'
);

CREATE TYPE ownership_type AS ENUM (
  'bootstrapped', 'vc_backed', 'pe_backed', 'public',
  'family_owned', 'state_owned', 'other'
);

CREATE TYPE geo_region AS ENUM (
  'dach', 'nordics', 'benelux', 'cee', 'uk_ireland',
  'southern_europe', 'us', 'other'
);

CREATE TYPE industry_enum AS ENUM (
  'software_saas', 'it', 'professional_services', 'financial_services',
  'healthcare', 'manufacturing', 'retail', 'media', 'energy',
  'telecom', 'transport', 'construction', 'education', 'public_sector', 'other'
);

CREATE TYPE revenue_range AS ENUM (
  'micro', 'small', 'medium', 'mid_market', 'enterprise'
);

CREATE TYPE buying_stage AS ENUM (
  'unaware', 'problem_aware', 'exploring_ai', 'looking_for_partners',
  'in_discussion', 'proposal_sent', 'won', 'lost'
);

CREATE TYPE engagement_status AS ENUM (
  'cold', 'approached', 'prospect', 'customer', 'churned'
);

CREATE TYPE crm_status_enum AS ENUM (
  'cold', 'scheduled_for_outreach', 'outreach', 'prospect', 'customer', 'churn'
);

CREATE TYPE confidence_level AS ENUM ('low', 'medium', 'high');

CREATE TYPE business_type AS ENUM (
  'manufacturer', 'distributor', 'service_provider', 'saas', 'platform', 'other'
);

CREATE TYPE cohort_enum AS ENUM ('a', 'b');

CREATE TYPE seniority_level AS ENUM (
  'c_level', 'vp', 'director', 'manager', 'individual_contributor', 'founder', 'other'
);

CREATE TYPE department_enum AS ENUM (
  'executive', 'engineering', 'product', 'sales', 'marketing',
  'customer_success', 'finance', 'hr', 'operations', 'other'
);

CREATE TYPE icp_fit AS ENUM ('strong_fit', 'moderate_fit', 'weak_fit', 'unknown');

CREATE TYPE relationship_status AS ENUM (
  'prospect', 'active', 'dormant', 'former', 'partner', 'internal'
);

CREATE TYPE contact_source AS ENUM (
  'inbound', 'outbound', 'referral', 'event', 'social', 'other'
);

CREATE TYPE contact_message_status AS ENUM (
  'not_started', 'generating', 'pending_review', 'approved', 'sent',
  'replied', 'no_channel', 'generation_failed'
);

CREATE TYPE message_channel AS ENUM (
  'linkedin_connect', 'linkedin_message', 'email', 'call_script'
);

CREATE TYPE message_review_status AS ENUM (
  'draft', 'approved', 'rejected', 'sent', 'delivered', 'replied'
);

CREATE TYPE message_tone AS ENUM ('professional', 'casual', 'bold', 'empathetic');
CREATE TYPE message_variant AS ENUM ('a', 'b');
CREATE TYPE language_enum AS ENUM ('en', 'de', 'nl', 'cs');

CREATE TYPE activity_source AS ENUM ('email', 'linkedin', 'call', 'in_person', 'manual');
CREATE TYPE activity_type_enum AS ENUM ('message', 'event');

CREATE TYPE crm_event_type AS ENUM (
  'meeting', 'call', 'email', 'demo', 'follow_up', 'intro', 'note', 'other'
);
CREATE TYPE crm_event_outcome AS ENUM (
  'scheduled', 'completed', 'postponed', 'cancelled', 'action_required'
);

CREATE TYPE tag_category AS ENUM (
  'risk_exclusion_flag', 'opportunity_theme', 'trigger_event',
  'ai_use_case', 'pain_area', 'opportunity_area', 'strategic_signal'
);

CREATE TYPE campaign_channel AS ENUM ('linkedin', 'email', 'multi');

-- ── TENANTS ──────────────────────────────────────────────────

CREATE TABLE tenants (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name        TEXT NOT NULL,
  slug        TEXT NOT NULL UNIQUE,
  domain      TEXT,
  settings    JSONB DEFAULT '{}',
  is_active   BOOLEAN DEFAULT true,
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now()
);

-- ── OWNERS ───────────────────────────────────────────────────

CREATE TABLE owners (
  id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id               UUID NOT NULL REFERENCES tenants(id),
  name                    TEXT NOT NULL,
  email                   TEXT,
  linkedin_profile_url    TEXT,
  signature_block         TEXT,
  lemlist_configured      BOOLEAN DEFAULT false,
  lemlist_default_campaign TEXT,
  default_tone            message_tone,
  default_language        language_enum DEFAULT 'en',
  is_active               BOOLEAN DEFAULT true,
  created_at              TIMESTAMPTZ DEFAULT now(),
  updated_at              TIMESTAMPTZ DEFAULT now(),
  airtable_record_id      TEXT,
  UNIQUE (tenant_id, email)
);
CREATE INDEX idx_owners_tenant ON owners(tenant_id);

-- ── BATCHES ──────────────────────────────────────────────────

CREATE TABLE batches (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id   UUID NOT NULL REFERENCES tenants(id),
  name        TEXT NOT NULL,
  description TEXT,
  owner_id    UUID REFERENCES owners(id),
  is_active   BOOLEAN DEFAULT true,
  created_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE (tenant_id, name)
);
CREATE INDEX idx_batches_tenant ON batches(tenant_id);

-- ── COMPANIES ────────────────────────────────────────────────

CREATE TABLE companies (
  id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id               UUID NOT NULL REFERENCES tenants(id),
  name                    TEXT NOT NULL,
  domain                  TEXT,
  batch_id                UUID REFERENCES batches(id),
  owner_id                UUID REFERENCES owners(id),

  -- Classification
  status                  company_status DEFAULT 'new',
  tier                    company_tier,
  business_model          business_model,
  company_size            company_size,
  ownership_type          ownership_type,
  geo_region              geo_region,
  industry                industry_enum,
  industry_category       TEXT,
  revenue_range           revenue_range,
  buying_stage            buying_stage,
  engagement_status       engagement_status,
  crm_status              crm_status_enum,
  ai_adoption             confidence_level,
  news_confidence         confidence_level,
  business_type           business_type,
  cohort                  cohort_enum,

  -- L1 results (lightweight)
  summary                 TEXT,
  hq_city                 TEXT,
  hq_country              TEXT,
  triage_notes            TEXT,
  triage_score            NUMERIC(4,1),
  verified_revenue_eur_m  NUMERIC(10,1),
  verified_employees      NUMERIC(10,1),
  enrichment_cost_usd     NUMERIC(10,4) DEFAULT 0,
  pre_score               NUMERIC(4,1),
  batch_number            NUMERIC(4,1),

  -- Flags
  lemlist_synced          BOOLEAN DEFAULT false,
  error_message           TEXT,
  notes                   TEXT,

  created_at              TIMESTAMPTZ DEFAULT now(),
  updated_at              TIMESTAMPTZ DEFAULT now(),
  airtable_record_id      TEXT
);

CREATE INDEX idx_companies_tenant_status ON companies(tenant_id, status);
CREATE INDEX idx_companies_tenant_batch ON companies(tenant_id, batch_id);
CREATE INDEX idx_companies_tenant_tier ON companies(tenant_id, tier);
CREATE INDEX idx_companies_domain ON companies(tenant_id, domain);
CREATE INDEX idx_companies_airtable ON companies(airtable_record_id) WHERE airtable_record_id IS NOT NULL;

-- ── COMPANY ENRICHMENT L2 (1:1) ─────────────────────────────

CREATE TABLE company_enrichment_l2 (
  company_id              UUID PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
  company_intel           TEXT,
  recent_news             TEXT,
  ai_opportunities        TEXT,
  pain_hypothesis         TEXT,
  relevant_case_study     TEXT,
  digital_initiatives     TEXT,
  leadership_changes      TEXT,
  hiring_signals          TEXT,
  key_products            TEXT,
  customer_segments       TEXT,
  competitors             TEXT,
  tech_stack              TEXT,
  funding_history         TEXT,
  eu_grants               TEXT,
  leadership_team         TEXT,
  ai_hiring               TEXT,
  tech_partnerships       TEXT,
  certifications          TEXT,
  quick_wins              JSONB,
  industry_pain_points    TEXT,
  cross_functional_pain   TEXT,
  adoption_barriers       TEXT,
  competitor_ai_moves     TEXT,
  enriched_at             TIMESTAMPTZ,
  enrichment_cost_usd     NUMERIC(10,4) DEFAULT 0,
  created_at              TIMESTAMPTZ DEFAULT now(),
  updated_at              TIMESTAMPTZ DEFAULT now()
);

-- ── COMPANY TAGS ─────────────────────────────────────────────

CREATE TABLE company_tags (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  company_id  UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  category    tag_category NOT NULL,
  value       TEXT NOT NULL,
  UNIQUE (company_id, category, value)
);
CREATE INDEX idx_company_tags_company ON company_tags(company_id);
CREATE INDEX idx_company_tags_lookup ON company_tags(category, value);

-- ── CONTACTS ─────────────────────────────────────────────────

CREATE TABLE contacts (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id             UUID NOT NULL REFERENCES tenants(id),
  company_id            UUID REFERENCES companies(id),
  owner_id              UUID REFERENCES owners(id),
  batch_id              UUID REFERENCES batches(id),

  full_name             TEXT NOT NULL,
  job_title             TEXT,
  email_address         TEXT,
  linkedin_url          TEXT,
  phone_number          TEXT,
  profile_photo_url     TEXT,

  seniority_level       seniority_level,
  department            department_enum,
  location_city         TEXT,
  location_country      TEXT,
  icp_fit               icp_fit DEFAULT 'unknown',
  relationship_status   relationship_status DEFAULT 'prospect',
  contact_source        contact_source,
  language              language_enum DEFAULT 'en',
  message_status        contact_message_status DEFAULT 'not_started',

  ai_champion           BOOLEAN DEFAULT false,
  ai_champion_score     SMALLINT,
  authority_score       SMALLINT,
  contact_score         SMALLINT,

  enrichment_cost_usd   NUMERIC(10,4) DEFAULT 0,
  processed_enrich      BOOLEAN DEFAULT false,
  email_lookup          BOOLEAN DEFAULT false,
  duplicity_check       BOOLEAN DEFAULT false,
  duplicity_conflict    BOOLEAN DEFAULT false,
  duplicity_detail      TEXT,
  notes                 TEXT,
  error                 TEXT,

  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now(),
  airtable_record_id    TEXT
);

CREATE INDEX idx_contacts_tenant_batch ON contacts(tenant_id, batch_id);
CREATE INDEX idx_contacts_tenant_company ON contacts(tenant_id, company_id);
CREATE INDEX idx_contacts_unprocessed ON contacts(tenant_id, batch_id) WHERE NOT processed_enrich;
CREATE INDEX idx_contacts_tenant_owner ON contacts(tenant_id, owner_id);
CREATE INDEX idx_contacts_email ON contacts(tenant_id, email_address) WHERE email_address IS NOT NULL;
CREATE INDEX idx_contacts_airtable ON contacts(airtable_record_id) WHERE airtable_record_id IS NOT NULL;

-- ── CONTACT ENRICHMENT (1:1) ─────────────────────────────────

CREATE TABLE contact_enrichment (
  contact_id              UUID PRIMARY KEY REFERENCES contacts(id) ON DELETE CASCADE,
  person_summary          TEXT,
  linkedin_profile_summary TEXT,
  relationship_synthesis  TEXT,
  enriched_at             TIMESTAMPTZ,
  enrichment_cost_usd     NUMERIC(10,4) DEFAULT 0,
  created_at              TIMESTAMPTZ DEFAULT now(),
  updated_at              TIMESTAMPTZ DEFAULT now()
);

-- ── CAMPAIGNS ────────────────────────────────────────────────

CREATE TABLE campaigns (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id             UUID NOT NULL REFERENCES tenants(id),
  owner_id              UUID REFERENCES owners(id),
  name                  TEXT NOT NULL,
  lemlist_campaign_id   TEXT,
  channel               campaign_channel,
  batch_id              UUID REFERENCES batches(id),
  is_active             BOOLEAN DEFAULT true,
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now(),
  airtable_record_id    TEXT
);
CREATE INDEX idx_campaigns_tenant ON campaigns(tenant_id);

-- ── MESSAGES ─────────────────────────────────────────────────

CREATE TABLE messages (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id             UUID NOT NULL REFERENCES tenants(id),
  contact_id            UUID NOT NULL REFERENCES contacts(id),
  owner_id              UUID REFERENCES owners(id),
  campaign_id           UUID REFERENCES campaigns(id),
  label                 TEXT,
  channel               message_channel NOT NULL,
  sequence_step         SMALLINT NOT NULL DEFAULT 1,
  variant               message_variant DEFAULT 'a',
  subject               TEXT,
  body                  TEXT NOT NULL,
  status                message_review_status DEFAULT 'draft',
  tone                  message_tone,
  language              language_enum DEFAULT 'en',
  generation_cost_usd   NUMERIC(10,4),
  approved_at           TIMESTAMPTZ,
  sent_at               TIMESTAMPTZ,
  batch_id              UUID REFERENCES batches(id),
  review_notes          TEXT,
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now(),
  airtable_record_id    TEXT
);
CREATE INDEX idx_messages_contact ON messages(contact_id);
CREATE INDEX idx_messages_tenant_status ON messages(tenant_id, status);
CREATE INDEX idx_messages_tenant_owner ON messages(tenant_id, owner_id, status);

-- ── ACTIVITIES ───────────────────────────────────────────────

CREATE TABLE activities (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id             UUID NOT NULL REFERENCES tenants(id),
  contact_id            UUID REFERENCES contacts(id),
  owner_id              UUID REFERENCES owners(id),
  activity_name         TEXT NOT NULL,
  source                activity_source,
  occurred_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  activity_type         activity_type_enum,
  activity_detail       TEXT,
  external_id           TEXT,
  processed             BOOLEAN DEFAULT false,
  batch_id              UUID REFERENCES batches(id),
  cost_usd              NUMERIC(10,4),
  created_at            TIMESTAMPTZ DEFAULT now(),
  airtable_record_id    TEXT
);
CREATE INDEX idx_activities_tenant ON activities(tenant_id);
CREATE INDEX idx_activities_contact ON activities(contact_id);
CREATE UNIQUE INDEX idx_activities_dedup ON activities(tenant_id, contact_id, source, occurred_at);

-- ── CRM EVENTS ───────────────────────────────────────────────

CREATE TABLE crm_events (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id             UUID NOT NULL REFERENCES tenants(id),
  event_name            TEXT NOT NULL,
  event_type            crm_event_type,
  event_date            TIMESTAMPTZ,
  company_id            UUID REFERENCES companies(id),
  summary               TEXT,
  event_outcome         crm_event_outcome,
  next_steps            TEXT,
  created_by            UUID REFERENCES owners(id),
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now(),
  airtable_record_id    TEXT
);
CREATE INDEX idx_crm_events_tenant ON crm_events(tenant_id);
CREATE INDEX idx_crm_events_company ON crm_events(company_id);

CREATE TABLE crm_event_participants (
  crm_event_id  UUID NOT NULL REFERENCES crm_events(id) ON DELETE CASCADE,
  contact_id    UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  PRIMARY KEY (crm_event_id, contact_id)
);

-- ── TASKS ────────────────────────────────────────────────────

CREATE TABLE tasks (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id             UUID NOT NULL REFERENCES tenants(id),
  task_name             TEXT NOT NULL,
  task_detail           TEXT,
  owner_id              UUID REFERENCES owners(id),
  scheduled_at          DATE,
  completed_at          DATE,
  completion_detail     TEXT,
  calendar_id           TEXT,
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now(),
  airtable_record_id    TEXT
);
CREATE INDEX idx_tasks_tenant ON tasks(tenant_id);
CREATE INDEX idx_tasks_open ON tasks(owner_id, scheduled_at) WHERE completed_at IS NULL;

CREATE TABLE task_contacts (
  task_id     UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  contact_id  UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  PRIMARY KEY (task_id, contact_id)
);

CREATE TABLE task_activities (
  task_id     UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  activity_id UUID NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
  PRIMARY KEY (task_id, activity_id)
);

-- ── RESEARCH ASSETS (polymorphic) ────────────────────────────

CREATE TABLE research_assets (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id             UUID NOT NULL REFERENCES tenants(id),
  entity_type           TEXT NOT NULL CHECK (entity_type IN ('company', 'contact')),
  entity_id             UUID NOT NULL,
  name                  TEXT NOT NULL,
  tool_name             TEXT,
  tool_config           TEXT,
  cost_usd              NUMERIC(10,4),
  research_data         TEXT,
  confidence_score      SMALLINT,
  quality_score         SMALLINT,
  created_at            TIMESTAMPTZ DEFAULT now(),
  airtable_record_id    TEXT
);
CREATE INDEX idx_research_assets_entity ON research_assets(entity_type, entity_id);
CREATE INDEX idx_research_assets_tenant ON research_assets(tenant_id);

-- ── PIPELINE RUNS ────────────────────────────────────────────

CREATE TABLE pipeline_runs (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id             UUID NOT NULL REFERENCES tenants(id),
  execution_id          TEXT,
  batch_id              UUID REFERENCES batches(id),
  owner_id              UUID REFERENCES owners(id),
  total_companies       INTEGER DEFAULT 0,
  total_contacts        INTEGER DEFAULT 0,
  l1_total              INTEGER DEFAULT 0,
  l1_done               INTEGER DEFAULT 0,
  l2_total              INTEGER DEFAULT 0,
  l2_done               INTEGER DEFAULT 0,
  person_total          INTEGER DEFAULT 0,
  person_done           INTEGER DEFAULT 0,
  cost_usd              NUMERIC(10,4) DEFAULT 0,
  status                TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
  config                JSONB DEFAULT '{}',
  started_at            TIMESTAMPTZ DEFAULT now(),
  completed_at          TIMESTAMPTZ,
  updated_at            TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_pipeline_runs_tenant ON pipeline_runs(tenant_id);

-- ── AUDIT LOG ────────────────────────────────────────────────

CREATE TABLE audit_log (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id   UUID REFERENCES tenants(id),
  table_name  TEXT NOT NULL,
  entity_id   UUID NOT NULL,
  field_name  TEXT,
  old_value   TEXT,
  new_value   TEXT,
  event       TEXT NOT NULL,
  changed_by  TEXT,
  changed_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_audit_log_entity ON audit_log(table_name, entity_id);
CREATE INDEX idx_audit_log_tenant_time ON audit_log(tenant_id, changed_at DESC);

-- ── TRIGGERS ─────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE tbl TEXT;
BEGIN
  FOR tbl IN SELECT unnest(ARRAY[
    'tenants','owners','companies','company_enrichment_l2',
    'contacts','contact_enrichment','campaigns','messages',
    'crm_events','tasks','pipeline_runs'
  ]) LOOP
    EXECUTE format(
      'CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %I
       FOR EACH ROW EXECUTE FUNCTION update_updated_at()', tbl, tbl);
  END LOOP;
END;$$;
