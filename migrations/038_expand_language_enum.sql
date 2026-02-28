-- 038: Expand language_enum from 4 to 13 values
-- LANG: Namespace Language Settings

ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'fr';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'es';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'it';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'pl';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'pt';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'sv';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'no';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'fi';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'da';
