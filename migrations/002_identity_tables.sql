-- ============================================================
-- Leadgen Pipeline - Identity Management
-- Migration: 002 - Users + Role-based Access Control
--
-- Depends on: 001_initial_schema.sql (tenants, owners tables)
-- Run: psql -d leadgen -f 002_identity_tables.sql
-- ============================================================

CREATE TYPE user_role AS ENUM ('admin', 'editor', 'viewer');

-- ── USERS ──────────────────────────────────────────────────

CREATE TABLE users (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email           TEXT NOT NULL UNIQUE,
  password_hash   TEXT NOT NULL,
  display_name    TEXT NOT NULL,
  is_super_admin  BOOLEAN DEFAULT false,
  is_active       BOOLEAN DEFAULT true,
  owner_id        UUID REFERENCES owners(id),
  last_login_at   TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_users_email ON users(email);

-- ── USER-TENANT ROLES ──────────────────────────────────────

CREATE TABLE user_tenant_roles (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  role        user_role NOT NULL DEFAULT 'viewer',
  granted_at  TIMESTAMPTZ DEFAULT now(),
  granted_by  UUID REFERENCES users(id),
  UNIQUE (user_id, tenant_id)
);

CREATE INDEX idx_user_tenant_roles_user ON user_tenant_roles(user_id);
CREATE INDEX idx_user_tenant_roles_tenant ON user_tenant_roles(tenant_id);

-- ── TRIGGERS ───────────────────────────────────────────────

CREATE TRIGGER trg_users_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
