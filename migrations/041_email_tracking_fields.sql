-- Migration 041: Add email engagement tracking fields to email_send_log
-- BL-174: Campaign analytics open/reply/bounce tracking

ALTER TABLE email_send_log ADD COLUMN IF NOT EXISTS opened_at TIMESTAMPTZ;
ALTER TABLE email_send_log ADD COLUMN IF NOT EXISTS open_count INTEGER DEFAULT 0;
ALTER TABLE email_send_log ADD COLUMN IF NOT EXISTS replied_at TIMESTAMPTZ;
ALTER TABLE email_send_log ADD COLUMN IF NOT EXISTS bounced_at TIMESTAMPTZ;
ALTER TABLE email_send_log ADD COLUMN IF NOT EXISTS bounce_type TEXT;  -- 'hard' or 'soft'
ALTER TABLE email_send_log ADD COLUMN IF NOT EXISTS clicked_at TIMESTAMPTZ;
ALTER TABLE email_send_log ADD COLUMN IF NOT EXISTS click_count INTEGER DEFAULT 0;
