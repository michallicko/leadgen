-- Add missing business_type enum values that the L1 enricher can produce
-- Note: ALTER TYPE ADD VALUE cannot run inside a transaction block
ALTER TYPE business_type ADD VALUE IF NOT EXISTS 'hybrid';
ALTER TYPE business_type ADD VALUE IF NOT EXISTS 'product_company';
ALTER TYPE business_type ADD VALUE IF NOT EXISTS 'service_company';
