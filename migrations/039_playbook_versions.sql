-- Migration 039: Extend strategy_versions for version browser feature (BL-1014)
--
-- Adds description and metadata columns to support Google Docs-style
-- version browsing with named snapshots and restore capabilities.

BEGIN;

ALTER TABLE strategy_versions
    ADD COLUMN IF NOT EXISTS description VARCHAR(255),
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

COMMIT;
