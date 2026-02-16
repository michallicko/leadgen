# Backlog

Structured backlog for the leadgen-pipeline project. Items are prioritized using MoSCoW and tracked with sequential IDs.

**Next ID**: BL-031

## Must Have

### BL-001: Contacts & Companies Screens
**Status**: Done | **Effort**: L | **Spec**: `docs/specs/contacts-companies-screens.md`
**Depends on**: — | **ADR**: `docs/adr/001-virtual-scroll-for-tables.md`

Dashboard screens for browsing, filtering, and viewing contacts and companies from the PostgreSQL database. Replaces direct Airtable access for day-to-day operations. Includes search, status filters, detail views, infinite scroll with virtual DOM windowing.

### BL-002: L1 Workflow Postgres Migration
**Status**: Refined | **Effort**: M | **Spec**: `docs/specs/l1-postgres-migration.md`
**Depends on**: — | **Theme**: Platform Foundation

Migrate the L1 Company enrichment n8n workflow to write directly to PostgreSQL instead of Airtable. First step in eliminating the Airtable dependency from the enrichment pipeline. Requires n8n Postgres credential setup and workflow node changes.

### BL-003: Full Workflow Migration (L2/Person/Orchestrator)
**Status**: Idea | **Effort**: XL | **Spec**: —
**Depends on**: BL-002 | **Theme**: Platform Foundation

Migrate remaining enrichment workflows (L2 Company, L2 Person, Orchestrator) to write to PostgreSQL. Completes the Airtable-to-Postgres transition. Cannot start until L1 migration (BL-002) is proven stable.

### BL-011: Import Phase 2 — Enrichment & Export
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: — | **Theme**: Contact Intelligence

Extends BL-006 import wizard with: enrichment depth selection (L1 only, L1+L2, full), credit cost estimation before execution, CSV/XLSX export of imported contacts. Surfaces enrichment options at import time so users can go from "raw CSV" to "enriched contacts" in one flow.

### BL-012: XLSX Import Support
**Status**: Idea | **Effort**: S | **Spec**: —
**Depends on**: — | **Theme**: Contact Intelligence

Add XLSX file parsing alongside existing CSV support in the import pipeline. Reuse the existing AI column mapper and dedup engine. Many small teams export from Excel, Google Sheets, or CRMs in XLSX format. Minimal new code — swap the parser, keep everything else.

### BL-013: Email Validation
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: — | **Theme**: Contact Intelligence

Validate contact email addresses: format check, MX record verification, disposable domain detection, and optional SMTP deliverability probe. Flag invalid/risky emails in the contact record. Run at import time and on-demand from the dashboard. Reduces bounce rates and improves sender reputation for outreach.

### BL-014: On-Demand Contact Enrichment
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: BL-015 | **Theme**: Contact Intelligence

Select contacts from the dashboard and trigger enrichment for missing fields via Perplexity/Claude. Shows credit cost estimate before execution. Progress tracking per contact. Results written back to contact/company records. First user-facing feature powered by the Python pipeline engine.

### BL-015: Python Pipeline Engine
**Status**: Idea | **Effort**: L | **Spec**: —
**Depends on**: BL-002 | **Theme**: Platform Foundation

Port enrichment pipeline stages from n8n to Python classes (L1Enrichment, L2Enrichment, PersonEnrichment, etc.). DB-backed job queue, built-in credit tracking, tenant-isolated execution contexts. Full test coverage per stage. Replaces n8n as the orchestration layer — see Technical Strategy Phase 2.

### BL-016: Modular Enrichment Framework
**Status**: Idea | **Effort**: L | **Spec**: —
**Depends on**: BL-015 | **Theme**: Contact Intelligence

Framework for modular, depth-selectable enrichment — the core of "AI company due diligence." Users choose which enrichment modules to run (company profile, legal, signals, news) and at what depth (quick scan vs full DD). Includes: module registry (pluggable enrichment stages), depth selector UI in dashboard, credit cost estimation before execution, progress tracking per module, and results viewer. Each module is a Python pipeline stage (via BL-015) that can be run independently or in combination.

### BL-017: Company Enrichment Modules
**Status**: In Progress | **Effort**: L | **Spec**: `docs/specs/ares-enrichment.md`
**Depends on**: BL-016 | **Theme**: Contact Intelligence

Four enrichment module packs for companies, each runnable independently via the modular framework (BL-016):
- **Company Profile**: Industry, size/headcount, what they do, tech stack, founding year, HQ, website analysis
- **Legal & Registry**: ~~Company registration number, directors/officers, filings, incorporation status, registered address, jurisdictions~~ **V1 done** — Czech ARES integration (ICO, DIC, legal form, directors, capital, NACE codes, insolvency). ADR-003.
- **Strategic Signals**: Funding rounds, M&A activity, hiring patterns (job postings), partnerships, growth indicators
- **News & PR**: Recent media mentions, press releases, social presence, thought leadership, sentiment

Each module uses Perplexity for research and Claude for analysis/structuring. Results stored as structured data with source citations.

### BL-018: Contact Enrichment Modules
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: BL-016 | **Theme**: Contact Intelligence

Enrichment modules for individual contacts, plugging into the modular framework (BL-016):
- **Role & Employment**: Current title verification, reporting structure, tenure (builds on BL-019)
- **Social & Online**: LinkedIn profile analysis, Twitter/X presence, speaking engagements, publications
- **Career History**: Previous roles, companies, career trajectory, industry experience
- **Contact Details**: Email verification (via BL-013), phone numbers, alternative contact methods

Depth selection: "basics" (role + email) vs "full profile" (all modules). Credit cost scales with depth.

### BL-030: Resend Email Integration (Dual-Mode)
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: — | **Theme**: Platform Foundation

Unified email sending via Resend with two delivery modes:
- **Platform mode**: Tenant verifies a sending subdomain (e.g., `outreach.acme.com`) on our Resend Scale account. We manage sending, they add 2 DNS records. Good for users without existing Resend.
- **BYOK mode**: If tenant's root domain is already claimed in another Resend account, they connect their own Resend API key. We validate their domain is verified, then send through their account directly. Zero cost to us, full root-domain sending for them.

Two use cases: (1) **Transactional** — enrichment notifications, import status, staleness alerts, weekly digests, account emails. (2) **Outreach delivery** — personalized emails to contacts, tracks opens/clicks/bounces, complements Lemlist.

Data model: `tenant_email_configs` table (mode, domain, subdomain, encrypted API key, verification status). Send logic checks mode and uses the appropriate Resend API key. Domain conflict auto-detected on registration attempt.

## Should Have

### BL-004: LinkedIn CSV Ingestion
**Status**: In Progress | **Effort**: S | **Spec**: —
**Depends on**: — | **Theme**: Contact Intelligence

Script to import LinkedIn Sales Navigator CSV exports into the contacts/companies tables. Enables bulk contact loading without manual Airtable entry. Handles deduplication by LinkedIn URL.

### BL-005: Stage Runs Tracking
**Status**: In Progress | **Effort**: M | **Spec**: —
**Depends on**: — | **Theme**: Closed-Loop Analytics

Database tables and API endpoints for tracking individual pipeline stage executions (L1, L2, Person). Records timing, status, error details, and cost per stage run. Enables pipeline observability beyond the current progress webhook.

### BL-006: Contact List Import & Cleanup
**Status**: Phase 1 Done | **Effort**: M | **Spec**: `docs/specs/contact-import-cleanup.md`
**Depends on**: — | **ADR**: `docs/adr/002-ai-column-mapping.md` | **Theme**: Contact Intelligence

Phase 1 (MVP): Upload CSV, AI column mapping, dedup preview, batch import. Phase 2 (future): enrichment depth selection, cost estimation, CSV export. Phase 3 (future): Person L1 verification workflow.

### BL-007: CRM Integration Framework
**Status**: Idea | **Effort**: L | **Spec**: —
**Depends on**: — | **Theme**: Platform Foundation

Bi-directional sync infrastructure for lightweight CRMs. Includes: OAuth2 connection manager (store/refresh tokens per tenant), configurable field mapping engine (our schema ↔ CRM schema), sync scheduler (periodic pull + push), conflict resolution strategy (last-write-wins or manual review), and sync status dashboard. Designed as a reusable framework — each CRM connector implements a standard adapter interface. Tracks sync history and provides audit trail.

### BL-008: HubSpot CRM Integration
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: BL-007 | **Theme**: Contact Intelligence

Bi-directional sync with HubSpot Free/Starter CRM via HubSpot API v3. Import contacts, companies, and deals. Push enriched data (company profile, enrichment results, tags) back to HubSpot properties. Map custom fields. Most popular free CRM in the startup ecosystem — covers the largest segment of our target market.

### BL-009: Pipedrive CRM Integration
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: BL-007 | **Theme**: Contact Intelligence

Bi-directional sync with Pipedrive via REST API. Import persons, organizations, and deals. Push enriched contact/company data back. Map custom fields and activity notes. Pipedrive is the go-to CRM for small outbound sales teams — strong fit with our "GTM engineering for small companies" positioning.

### BL-010: Notion CRM Integration
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: BL-007 | **Theme**: Contact Intelligence

Bi-directional sync with Notion databases via Notion API. User connects their Notion workspace, selects the database used as a CRM, and maps properties to our contact/company schema. Push enriched data back as property updates. Many startups and freelancers use Notion databases as a lightweight CRM — this meets them where they already work.

### BL-019: Employment Verification
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: BL-013, BL-015 | **Theme**: Contact Intelligence

Two-tier check to determine whether a contact still works at their listed company. Tier 1 (fast/cheap): email deliverability probe via BL-013 — if work email bounces, flag as likely departed. Tier 2 (thorough): AI research via Perplexity/Claude for inconclusive cases — checks LinkedIn profile, company website, recent news. Returns confidence score + evidence summary. Runnable on-demand per contact or in batch via the pipeline engine. Updates contact record with verification status and last-verified date.

### BL-020: Personal LinkedIn Connections Import
**Status**: Idea | **Effort**: S | **Spec**: —
**Depends on**: — | **Theme**: Contact Intelligence

Import contacts from LinkedIn "Download your data" archive (connections.csv format). Maps LinkedIn-specific fields (Connected On, Position, Company) to contact/company schema. Dedup by LinkedIn profile URL. Enables users to import their personal network as a lead source.

### BL-021: Data Normalization
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: — | **Theme**: Contact Intelligence

Standardize company names (e.g., "Google LLC" → "Google"), job titles (e.g., "VP Sales" → "Vice President of Sales"), and locations (e.g., "NYC" → "New York, NY, US") across all contacts. AI-assisted matching with manual override. Runs at import and on-demand. Improves dedup accuracy and filtering quality.

### BL-022: Bulk Dedup
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: — | **Theme**: Contact Intelligence

Find and merge duplicate contacts/companies across existing data — not just at import time. Dashboard UI shows clusters of potential duplicates with similarity scores. User picks merge strategy per cluster (keep newest, merge fields, skip). Prevents data rot as contacts accumulate from multiple sources.

### BL-023: Staleness Detection
**Status**: Idea | **Effort**: S | **Spec**: —
**Depends on**: — | **Theme**: Contact Intelligence

Flag contacts not updated in 30/60/90 days with visual indicators in the dashboard. Add "last_enriched_at" and "data_quality_score" fields to contacts. Filterable by staleness level. Surfaces which contacts need re-enrichment. Foundation for smart refresh (BL-024).

### BL-024: Google Drive Contact Import
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: — | **Theme**: Contact Intelligence

Import contacts from Google Drive spreadsheets (Sheets). OAuth2 integration with Google APIs. User connects their Google account, browses Drive for contact lists, and imports directly. Reuses existing AI column mapper and dedup engine. Eliminates the "export to CSV, then upload" step.

### BL-025: Gmail Contacts Import
**Status**: In Progress | **Effort**: M | **Spec**: —
**Depends on**: — | **Theme**: Contact Intelligence

Import contacts from Google Contacts (People API). OAuth2 via same Google integration as BL-024. Pulls name, email, company, phone, notes. Maps to contact/company schema. Dedup by email. Many freelancers and small teams use Gmail as their de facto CRM — this captures their existing network.

### BL-026: Gmail Email History Scan
**Status**: In Progress | **Effort**: L | **Spec**: —
**Depends on**: — | **Theme**: Contact Intelligence

Scan Gmail inbox/sent for contacts not in the database. Extract contact info from email headers (From/To/CC), signatures (title, phone, company), and email footers. AI-powered extraction for unstructured signature parsing. Surfaces "hidden" contacts the user has been emailing but never added to any CRM.

### BL-027: Outlook / Microsoft 365 Import
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: — | **Theme**: Contact Intelligence

Import contacts from Microsoft 365 / Outlook (Microsoft Graph API). OAuth2 via Microsoft identity platform. Pulls contacts, email history scan (similar to BL-026 for Gmail). Covers users in Microsoft-centric orgs. Shares extraction logic with Gmail scan where possible.

## Could Have

### BL-028: Influencer Signal Ingest
**Status**: Idea | **Effort**: L | **Spec**: —
**Depends on**: — | **Theme**: Contact Intelligence

Monitor engagement on a person-of-interest's LinkedIn posts. Capture commenters and likers as warm leads (they've shown intent by engaging with relevant content). Requires LinkedIn API or scraping strategy. Produces high-quality leads with built-in engagement signal. Potential standalone product feature.

### BL-029: Smart Contact Refresh (Two-Tier Cron)
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: BL-013, BL-015, BL-023 | **Theme**: Contact Intelligence

Cost-optimized scheduled contact freshness system. **Tier 1 (cheap cron)**: Periodic lightweight probes on critical time-sensitive attributes only — email deliverability (SMTP/MX check), LinkedIn profile delta detection (title/company changed), company domain/website status (still active, redirects, new content), and job posting signals (company hiring for the contact's role = possible departure). **Tier 2 (selective deep refresh)**: Only contacts where Tier 1 detects a change get flagged for full re-enrichment via the modular pipeline (BL-016). Configurable per tenant: scan frequency, credit budget cap, change sensitivity threshold. Optimizes for cost — spend credits only where something actually changed.

## Won't Have (for now)

_No items yet._

## Completed

### BL-001: Contacts & Companies Screens (Done 2026-02-13)
Dashboard screens with infinite scroll, virtual DOM windowing, filters, detail modals, inline editing. ADR-001.

### BL-006: Contact List Import & Cleanup — Phase 1 (Done 2026-02-13)
CSV upload with AI column mapping, dedup preview, batch import. 80 unit tests. ADR-002.
