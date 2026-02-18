-- Enrichment configuration templates and schedules
-- Allows saving named pipeline configurations for reuse and scheduling

create table if not exists enrichment_configs (
    id          uuid primary key default uuid_generate_v4(),
    tenant_id   uuid not null references tenants(id),
    name        text not null,
    description text default '',
    config      jsonb default '{}'::jsonb,
    is_default  boolean default false,
    created_by  uuid references users(id),
    created_at  timestamptz default now(),
    updated_at  timestamptz default now(),
    constraint uq_enrich_config_tenant_name unique (tenant_id, name)
);

create index if not exists idx_enrich_configs_tenant on enrichment_configs(tenant_id);

create table if not exists enrichment_schedules (
    id              uuid primary key default uuid_generate_v4(),
    tenant_id       uuid not null references tenants(id),
    config_id       uuid not null references enrichment_configs(id) on delete cascade,
    schedule_type   text not null,  -- 'cron' or 'on_new_entity'
    cron_expression text,
    tag_filter      text,
    is_active       boolean default true,
    last_run_at     timestamptz,
    next_run_at     timestamptz,
    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

create index if not exists idx_enrich_schedules_tenant on enrichment_schedules(tenant_id);
create index if not exists idx_enrich_schedules_config on enrichment_schedules(config_id);
