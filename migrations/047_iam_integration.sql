-- Migration 047: IAM integration columns
-- Adds iam_user_id and auth_provider to users table, makes password_hash nullable.

ALTER TABLE users ADD COLUMN IF NOT EXISTS iam_user_id TEXT UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider TEXT DEFAULT 'local';
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;

-- Partial index for efficient IAM user lookups (only index non-null values)
CREATE INDEX IF NOT EXISTS ix_users_iam_user_id ON users (iam_user_id) WHERE iam_user_id IS NOT NULL;
