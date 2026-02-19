-- 027: Add linkedin_activity_level to contacts
DO $$ BEGIN
  CREATE TYPE linkedin_activity_level AS ENUM ('active', 'moderate', 'quiet', 'unknown');
EXCEPTION WHEN duplicate_object THEN null;
END $$;

ALTER TABLE contacts ADD COLUMN IF NOT EXISTS linkedin_activity_level linkedin_activity_level DEFAULT 'unknown';
