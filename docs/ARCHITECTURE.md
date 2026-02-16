# Leadgen Pipeline - Architecture

> Last updated: 2026-02-16

## System Overview

Leadgen Pipeline is a multi-tenant B2B lead enrichment and outreach platform. It ingests company/contact lists, runs AI-powered enrichment through a multi-stage pipeline, generates personalized outreach messages, and provides a dashboard for review and management.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BROWSER (Dashboard)                          │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Pipeline  │  │ Messages │  │  Admin   │  │ Login / Auth     │   │
│  │ Control   │  │ Review   │  │ Panel    │  │ (JWT)            │   │
│  └─────┬─────┘  └─────┬────┘  └────┬─────┘  └─────────────────┘   │
│        │              │             │                                │
└────────┼──────────────┼─────────────┼───────────────────────────────┘
         │              │             │
    n8n webhooks    REST API      REST API
         │              │             │
┌────────┼──────────────┼─────────────┼───────────────────────────────┐
│        │    Caddy Reverse Proxy (leadgen.visionvolve.com)           │
│        │              │             │                                │
│   /webhook/*     /api/*        /api/*                               │
│        │              │             │                                │
│   ┌────▼────┐    ┌────▼─────────────▼────┐                         │
│   │   n8n   │    │   Flask API           │                         │
│   │ (5678)  │    │   (Gunicorn :5000)    │                         │
│   │         │    │                       │                         │
│   │ Orch.   │    │ - Auth (JWT/bcrypt)   │                         │
│   │ L1/L2   │    │ - Tenants CRUD        │                         │
│   │ Person  │    │ - Users CRUD          │                         │
│   │ Progress│    │ - Messages CRUD       │                         │
│   │         │    │ - Batches / Stats     │                         │
│   └────┬────┘    └────────┬──────────────┘                         │
│        │                  │                                         │
│        └──────┬───────────┘                                        │
│               │                                                     │
│        ┌──────▼──────┐                                             │
│        │  PostgreSQL  │                                             │
│        │  (RDS)       │                                             │
│        │              │                                             │
│        │  leadgen DB  │                                             │
│        └──────────────┘                                             │
│                                                                     │
│   Docker host: 52.58.119.191 (Amazon Linux 2023)                   │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Dashboard (Static Frontend)
- **Tech**: Vanilla HTML/JS/CSS, no build step
- **Hosting**: Caddy file server at `leadgen.visionvolve.com`
- **Pages**: `index.html` (Pipeline), `companies.html` (Companies), `contacts.html` (Contacts), `messages.html` (Messages), `import.html` (Import — CSV + Google), `enrich.html` (Enrichment Wizard), `llm-costs.html` (LLM Costs, super admin), `admin.html` (Admin)
- **Virtual scroll**: Companies and Contacts tables use DOM windowing — only ~60-80 rows rendered at any time regardless of dataset size. Data fetched via infinite scroll (IntersectionObserver), rendered via `renderWindow()` on scroll (see ADR-001)
- **Auth**: JWT stored in localStorage, managed by `auth.js`
- **Namespace routing**: `/{tenant-slug}/page` — Caddy strips prefix, JS reads namespace from URL

### 2. Flask API
- **Tech**: Flask + SQLAlchemy + Gunicorn
- **Container**: `leadgen-api` (Docker, port 5000)
- **Routes**: `/api/auth/*`, `/api/tenants/*`, `/api/users/*`, `/api/batches/*`, `/api/companies/*`, `/api/contacts/*`, `/api/messages/*`, `/api/pipeline/*`, `/api/imports/*`, `/api/llm-usage/*`, `/api/oauth/*`, `/api/gmail/*`, `/api/health`
- **Services**: `pipeline_engine.py` (stage orchestration), `ares.py` (Czech ARES registry lookups), `csv_mapper.py` (AI column mapping), `dedup.py` (contact/company deduplication), `llm_logger.py` (LLM usage cost tracking), `google_oauth.py` (OAuth token management), `google_contacts.py` (People API fetch/mapping), `gmail_scanner.py` (background Gmail scan + AI signature extraction)
- **Auth**: JWT Bearer tokens, bcrypt password hashing
- **Multi-tenant**: Shared PG schema, `tenant_id` on all entity tables

### 3. n8n Workflows
- **Tech**: n8n (self-hosted, Docker)
- **Orchestrator**: Multi-stage enrichment pipeline (L1 → Triage → L2 → Person)
- **Sub-workflows**: L1 Company, L2 Company, L2 Person (each called via Execute Workflow)
- **Support**: Progress Store (webhook-based progress tracking), Batch List/Stats APIs
- **Data**: Currently reads/writes Airtable (PG migration pending for workflow nodes)

### 4. PostgreSQL (RDS)
- **Instance**: AWS Lightsail managed PostgreSQL
- **Databases**: `n8n` (n8n internal), `leadgen` (application data)
- **Schema**: 18 entity tables + 3 junction tables + 2 auth tables, ~30 enum types
- **Multi-tenant**: `tenant_id` column on all entity tables
- **DDL**: `migrations/001_initial_schema.sql` through `012_company_registry_data.sql`

### 5. Caddy (Reverse Proxy)
- **Subdomains**: `n8n.visionvolve.com`, `leadgen.visionvolve.com`, `vps.visionvolve.com`, `ds.visionvolve.com`
- **Leadgen routing**: `/api/*` → Flask API, everything else → static dashboard files
- **Namespace routing**: `/{slug}/page` → strips prefix → serves `/page.html`
- **TLS**: Automatic via Let's Encrypt

## Data Flow

### Enrichment Pipeline
```
Trigger (webhook)
    │
    ▼
Load Contacts (Airtable) ──→ Gate Logic (route by status)
    │                              │
    ├──→ L1 Enrichment ──→ Triage  │
    │                              │
    ├──→ L2 Enrichment ────────────┤
    │                              │
    ├──→ Person Enrichment ────────┤
    │                              │
    └──→ Done (mark complete) ◄────┘
```

### Authentication Flow
```
Browser → POST /api/auth/login {email, password}
    │
    ▼
Flask API → bcrypt verify → JWT (access + refresh)
    │
    ▼
Browser stores tokens in localStorage
    │
    ▼
Subsequent requests: Authorization: Bearer {access_token}
    │
    ▼
Token expired → POST /api/auth/refresh {refresh_token}
```

### Google OAuth + Gmail Import Flow
```
Dashboard → GET /api/oauth/google/auth-url
    │
    ▼
Browser → Google OAuth consent screen (contacts.readonly + gmail.readonly)
    │
    ▼
Google callback → GET /api/oauth/google/callback?code=...
    │
    ▼
Flask API → exchange code → encrypt tokens (Fernet) → store in oauth_connections
    │
    ▼
Google Contacts: POST /api/gmail/contacts/fetch → People API → dedup preview → import
    │
Gmail Scan: POST /api/gmail/scan/start → background thread:
    ├── Scan message headers (From/To/CC) — deterministic
    ├── Extract signatures via Claude Haiku — batched AI
    ├── Aggregate by email → contact rows
    └── dedup preview → import
```

## Database Schema (High Level)

```
tenants ─┬── owners
         ├── batches
         ├── import_jobs (CSV/Gmail import lifecycle tracking)
         ├── oauth_connections (Google OAuth tokens, Fernet-encrypted)
         ├── companies ─┬── company_enrichment_l2 (1:1)
         │              ├── company_registry_data (1:1, ARES)
         │              └── company_tags (1:∞)
         ├── contacts ──── contact_enrichment (1:1)
         ├── messages
         ├── campaigns
         ├── activities
         ├── crm_events ── crm_event_participants
         ├── tasks ─┬── task_contacts
         │          └── task_activities
         ├── research_assets (polymorphic)
         ├── pipeline_runs
         ├── llm_usage_log (per-call LLM cost tracking)
         └── audit_log

users ── user_tenant_roles ── tenants
     └── oauth_connections (per-user, per-provider)
```

## Deployment

| Component | Deploy Command | Container |
|-----------|---------------|-----------|
| Dashboard | `bash deploy/deploy-dashboard.sh` | Caddy (static files) |
| API | `bash deploy/deploy-api.sh` | `leadgen-api` |
| Caddy config | `cd visionvolve-vps && bash scripts/deploy-caddy.sh` | `caddy` |
| n8n workflows | Via n8n UI or API | `n8n` |

## External Dependencies

- **Airtable**: Data store for n8n workflows (dashboard APIs migrated to PG)
- **ARES (ares.gov.cz)**: Czech public business register — ICO/DIC lookup, name search, commercial register (directors, capital). Free government API, no authentication. Used by the `ares` pipeline stage for Czech company enrichment.
- **Google APIs**: OAuth 2.0 (identity), People API (contacts), Gmail API (email scan)
- **Perplexity API**: L1/L2 company research
- **Anthropic API**: AI analysis, message generation, email signature extraction (Haiku)
- **Lemlist**: Outreach campaign delivery
- **AWS RDS**: PostgreSQL hosting
