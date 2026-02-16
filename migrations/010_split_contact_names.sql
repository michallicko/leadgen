-- Migration 010: Split contacts.full_name into first_name + last_name
-- This enables direct CSV column mapping without combine_first_last transform.

ALTER TABLE contacts ADD COLUMN first_name TEXT;
ALTER TABLE contacts ADD COLUMN last_name TEXT;

UPDATE contacts SET
  first_name = CASE
    WHEN position(' ' IN full_name) > 0
    THEN substring(full_name FROM 1 FOR position(' ' IN full_name) - 1)
    ELSE full_name
  END,
  last_name = CASE
    WHEN position(' ' IN full_name) > 0
    THEN trim(substring(full_name FROM position(' ' IN full_name) + 1))
    ELSE ''
  END;

ALTER TABLE contacts ALTER COLUMN first_name SET NOT NULL;
ALTER TABLE contacts ALTER COLUMN last_name SET NOT NULL;
ALTER TABLE contacts ALTER COLUMN last_name SET DEFAULT '';
ALTER TABLE contacts DROP COLUMN full_name;
