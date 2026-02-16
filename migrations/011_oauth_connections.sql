-- 011: OAuth connections + ImportJob extensions for Gmail/Google Contacts import
-- Depends on: 007_import_jobs.sql

begin;

-- OAuth connections table
create table if not exists oauth_connections (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references users(id) on delete cascade,
    tenant_id uuid not null references tenants(id) on delete cascade,
    provider text not null,  -- 'google', 'microsoft', 'hubspot'
    provider_account_id text,
    provider_email text,
    access_token_enc text,
    refresh_token_enc text,
    token_expiry timestamptz,
    scopes text[],
    status text not null default 'active',  -- active, revoked, expired
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_oauth_user_provider_account
        unique (user_id, tenant_id, provider, provider_account_id)
);

create index if not exists idx_oauth_connections_user
    on oauth_connections(user_id, tenant_id);

-- Extend import_jobs with source type and OAuth link
alter table import_jobs
    add column if not exists source text not null default 'csv',
    add column if not exists oauth_connection_id uuid references oauth_connections(id),
    add column if not exists scan_config jsonb default '{}'::jsonb,
    add column if not exists scan_progress jsonb default '{}'::jsonb;

commit;
