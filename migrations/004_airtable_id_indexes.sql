-- ============================================================
-- Migration 004: Unique partial indexes on airtable_record_id
-- Enables idempotent upserts (ON CONFLICT) during data migration
--
-- Run: psql -d leadgen -f 004_airtable_id_indexes.sql
-- ============================================================

CREATE UNIQUE INDEX IF NOT EXISTS uq_owners_airtable
  ON owners(airtable_record_id) WHERE airtable_record_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_airtable
  ON companies(airtable_record_id) WHERE airtable_record_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_contacts_airtable
  ON contacts(airtable_record_id) WHERE airtable_record_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_messages_airtable
  ON messages(airtable_record_id) WHERE airtable_record_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_batches_airtable
  ON batches(tenant_id, name);

CREATE UNIQUE INDEX IF NOT EXISTS uq_campaigns_airtable
  ON campaigns(airtable_record_id) WHERE airtable_record_id IS NOT NULL;
