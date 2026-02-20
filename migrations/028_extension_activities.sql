-- Migration 028: Extend activities table for browser extension support + contacts stub fields
-- The activities table already exists (migration 001). This adds new columns needed
-- by the extension feature and relaxes constraints for the new usage pattern.

-- 1. Add new columns for extension activities
ALTER TABLE activities ADD COLUMN IF NOT EXISTS event_type TEXT;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS timestamp TIMESTAMPTZ;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS payload JSONB DEFAULT '{}';

-- 2. Backfill event_type from existing activity_type enum for old rows, then make NOT NULL
UPDATE activities SET event_type = COALESCE(activity_type::text, 'event') WHERE event_type IS NULL;
ALTER TABLE activities ALTER COLUMN event_type SET NOT NULL;
ALTER TABLE activities ALTER COLUMN event_type SET DEFAULT 'event';

-- 3. Change source from activity_source enum to TEXT (supports 'linkedin_extension' and future values)
ALTER TABLE activities ALTER COLUMN source TYPE TEXT USING source::text;

-- 4. Relax activity_name NOT NULL constraint (extension activities may not have one)
ALTER TABLE activities ALTER COLUMN activity_name DROP NOT NULL;

-- 5. New indexes for extension query patterns (skip if already exists)
CREATE UNIQUE INDEX IF NOT EXISTS idx_activities_tenant_external_id
    ON activities(tenant_id, external_id) WHERE external_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_activities_tenant_contact
    ON activities(tenant_id, contact_id);
CREATE INDEX IF NOT EXISTS idx_activities_tenant_type_ts
    ON activities(tenant_id, event_type, timestamp);
CREATE INDEX IF NOT EXISTS idx_activities_tenant_source
    ON activities(tenant_id, source);

-- 6. Contact stub fields for extension lead import
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS is_stub BOOLEAN DEFAULT false;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS import_source TEXT;

-- Index for finding stub contacts
CREATE INDEX IF NOT EXISTS idx_contacts_is_stub
    ON contacts(tenant_id, is_stub) WHERE is_stub = true;
