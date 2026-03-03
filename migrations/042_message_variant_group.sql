-- BL-181: Add variant_group column to messages for A/B variant linking
-- Messages generated together for the same contact+step share a variant_group UUID.

ALTER TABLE messages ADD COLUMN IF NOT EXISTS variant_group UUID;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS variant_angle TEXT;

-- Index for efficient variant group lookups
CREATE INDEX IF NOT EXISTS idx_messages_variant_group ON messages(variant_group) WHERE variant_group IS NOT NULL;
