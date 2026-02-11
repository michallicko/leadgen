-- ============================================================
-- Leadgen Pipeline - Seed VisionVolve Namespace
-- Migration: 003 - Create default tenant + link super admins
--
-- Depends on: 002_identity_tables.sql
-- Run: psql -d leadgen -f 003_seed_visionvolve.sql
-- ============================================================

-- ── SUPER ADMIN USER ─────────────────────────────────────────
-- Temp password: ChangeMeNow2026!  (change immediately after first login)

INSERT INTO users (email, password_hash, display_name, is_super_admin)
VALUES (
  'michal@visionvolve.ai',
  '$2b$12$uXg1Y0KK/5ZIoCZy15FKq.ydEdQ6F0aYf/MS72NfpAFvRQUBkBtX2',
  'Michal',
  true
)
ON CONFLICT (email) DO UPDATE SET is_super_admin = true;

-- ── INSERT DEFAULT TENANT ────────────────────────────────────

INSERT INTO tenants (name, slug, domain)
VALUES ('VisionVolve', 'visionvolve', 'visionvolve.com')
ON CONFLICT (slug) DO NOTHING;

-- ── LINK ALL SUPER ADMINS AS NAMESPACE ADMINS ────────────────

INSERT INTO user_tenant_roles (user_id, tenant_id, role)
SELECT u.id, t.id, 'admin'
FROM users u
CROSS JOIN tenants t
WHERE u.is_super_admin = true
  AND t.slug = 'visionvolve'
  AND NOT EXISTS (
    SELECT 1 FROM user_tenant_roles utr
    WHERE utr.user_id = u.id AND utr.tenant_id = t.id
  );
