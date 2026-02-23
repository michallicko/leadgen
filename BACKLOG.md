# Backlog

Structured backlog for the leadgen-pipeline project. Items are prioritized using MoSCoW and tracked with sequential IDs.

**Next ID**: BL-053

## Must Have

### BL-001: Contacts & Companies Screens
**Status**: Done | **Effort**: L | **Spec**: `docs/specs/contacts-companies-screens.md`
**Depends on**: — | **ADR**: `docs/adr/001-virtual-scroll-for-tables.md`

Dashboard screens for browsing, filtering, and viewing contacts and companies from the PostgreSQL database. Replaces direct Airtable access for day-to-day operations. Includes search, status filters, detail views, infinite scroll with virtual DOM windowing.

### BL-002: L1 Workflow Postgres Migration
**Status**: Done | **Effort**: M | **Spec**: `docs/specs/l1-native-enrichment.md`
**Depends on**: — | **Theme**: Platform Foundation

Migrate the L1 Company enrichment from n8n to native Python. L1 enricher (`l1_enricher.py`) with Perplexity sonar API, QC validation (8 checks), research storage, review workflow, LinkedIn context. Deployed and QC'd against real data. PR #1 merged 2026-02-16.

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
**Status**: In Progress | **Effort**: L | **Spec**: —
**Depends on**: BL-002 | **Theme**: Platform Foundation

Port enrichment pipeline stages from n8n to Python. L1 stage ported (ADR-003). Hybrid dispatch: `_process_entity()` routes L1 to native Python, L2/Person/Generate still via n8n webhooks. Remaining: port L2, Person, Generate stages.

### BL-016: Modular Enrichment Framework
**Status**: Idea | **Effort**: L | **Spec**: —
**Depends on**: BL-015 | **Theme**: Contact Intelligence

Framework for modular, depth-selectable enrichment — the core of "AI company due diligence." Users choose which enrichment modules to run (company profile, legal, signals, news) and at what depth (quick scan vs full DD). Includes: module registry (pluggable enrichment stages), depth selector UI in dashboard, credit cost estimation before execution, progress tracking per module, and results viewer. Each module is a Python pipeline stage (via BL-015) that can be run independently or in combination.

### BL-017: Company Enrichment Modules
**Status**: In Progress | **Effort**: L | **Spec**: `docs/specs/ares-enrichment.md`
**Depends on**: BL-016 | **Theme**: Contact Intelligence

Four enrichment module packs for companies, each runnable independently via the modular framework (BL-016):
- **Company Profile**: Industry, size/headcount, what they do, tech stack, founding year, HQ, website analysis
- **Legal & Registry**: **V2 done** — Unified `registry` stage via `RegistryOrchestrator` (ADR-005). Auto-detects country, runs applicable adapters (CZ ARES, NO BRREG, FI PRH, FR recherche, CZ ISIR) in dependency order. Credibility score 0-100. Unified `company_legal_profile` table. Dashboard shows single "Legal & Registry" card with credibility badge.
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

### BL-052: Contact Filtering, Selection & Campaign Management via Chat + UI
**Status**: Spec'd | **Effort**: L | **Spec**: `docs/specs/contact-campaign-management.md`
**Depends on**: AGENT (agent-ready chat), PB-001 (phase infrastructure) | **Theme**: Outreach Engine

Users can filter/select contacts and create or assign them to campaigns through BOTH AI chat tools and traditional UI. Chat tools: `filter_contacts`, `create_campaign`, `assign_to_campaign`, `check_strategy_conflicts`. UI: faceted filter panel, contact table with checkboxes, campaign creation modal. AI proactively flags ALL strategy conflicts: ICP mismatch, channel gaps, segment overlap with active campaigns, timing/cooldown violations, and tone mismatches. Campaigns become internal (no Lemlist dependency). Strategy document links to campaigns for ICP-aware conflict detection.

### BL-031: Campaign CRUD + Data Model
**Status**: Done | **Effort**: M | **Spec**: `docs/specs/campaign-crud.md`
**Depends on**: — | **ADR**: `docs/adr/006-campaign-data-model.md` | **Theme**: Outreach Engine

Extend campaigns table with status, template config, generation config. New campaign_contacts junction table and campaign_templates table. CRUD API endpoints + CampaignsPage under Reach pillar. Foundation for message generation pipeline.

### BL-032: Assign Contacts to Campaign
**Status**: Done | **Effort**: M | **Spec**: —
**Depends on**: BL-031 | **Theme**: Outreach Engine

Contact picker with filters (batch, company, owner, tags). Add/remove contacts from campaign. Duplicate detection. Campaign detail shows contact count.

### BL-033: Configure Message Types (Template Presets)
**Status**: Done | **Effort**: M | **Spec**: —
**Depends on**: BL-031 | **Theme**: Outreach Engine

Template preset selector (LinkedIn + Email, Email 3-Step, LinkedIn Only). Toggle steps on/off. Configure tone, language, custom instructions. System templates seeded in migration.

### BL-034: Enrichment Readiness Check
**Status**: Done | **Effort**: S | **Spec**: —
**Depends on**: BL-032 | **Theme**: Outreach Engine

API endpoint checking entity_stage_completions per campaign contact. Returns readiness summary (X/Y ready, Z need enrichment). Cost estimate for missing enrichment.

### BL-035: Message Generation Engine
**Status**: Done | **Effort**: XL | **Spec**: —
**Depends on**: BL-032, BL-033 | **Theme**: Outreach Engine

Core generation service. Background thread processes contacts, calls Claude API per message step, writes to messages table. Channel-specific constraints, prompt templates, cost logging, progress tracking.

### BL-036: Review Campaign Messages
**Status**: Done | **Effort**: S | **Spec**: —
**Depends on**: BL-035 | **Theme**: Outreach Engine

Campaign filter on Messages page. Campaign-level bulk approve. Campaign detail shows generated/approved/rejected counts.

### BL-045: Message Review Workflow
**Status**: In Progress | **Effort**: XL | **Spec**: `docs/specs/message-review-workflow/`
**Depends on**: BL-035, BL-036 | **Theme**: Outreach Engine

Enhanced review with focused single-message queue (must approve/reject to advance), per-message regeneration (language, formality, tone, custom instruction), version tracking with tagged edit feedback for LLM training, contact disqualification (campaign-only or global), and campaign outreach approval gate.

### BL-037: Template Library
**Status**: Idea | **Effort**: S | **Spec**: —
**Depends on**: BL-031 | **Theme**: Outreach Engine

Save current campaign config as reusable template. Load template into new campaign.

### BL-038: Clone Campaign
**Status**: Idea | **Effort**: S | **Spec**: —
**Depends on**: BL-031 | **Theme**: Outreach Engine

Clone campaign config (not contacts or messages). New campaign starts as draft.

### BL-039: Lemlist CSV Export
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: BL-036 | **Theme**: Outreach Engine

Export approved messages as Lemlist-compatible CSV. Columns: email, firstName, lastName, companyName, + custom columns per step.

### BL-040: LinkedIn Export
**Status**: Idea | **Effort**: S | **Spec**: —
**Depends on**: BL-036 | **Theme**: Outreach Engine

Export approved LinkedIn messages as CSV: full_name, linkedin_url, connection_message, followup_message.

### BL-041: PDF Template Upload
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: BL-031 | **Theme**: Outreach Engine

HTML template upload with {{variable}} placeholders. Variable picker shows available enrichment fields. Templates stored per tenant.

### BL-042: PDF Generation
**Status**: Idea | **Effort**: L | **Spec**: —
**Depends on**: BL-041, BL-035 | **Theme**: Outreach Engine

Render personalized PDF per contact from template + enrichment data. Stored as file, URL attached to message.

### BL-043: A/B Variant Generation
**Status**: Idea | **Effort**: M | **Spec**: —
**Depends on**: BL-035 | **Theme**: Outreach Engine

Generate 2 variants per step (different angles/temperature). Both shown in review. Cost doubles for 2-variant steps.

### BL-044: Custom Prompt Instructions
**Status**: Idea | **Effort**: S | **Spec**: —
**Depends on**: BL-035 | **Theme**: Outreach Engine

Per-campaign instruction text appended to generation prompts. Max 2000 chars.

### BL-049: Playbook Auto-Save (Debounced)
**Status**: Idea | **Effort**: S | **Spec**: —
**Depends on**: — | **Theme**: Outreach Engine

Replace the explicit save button in the Playbook editor with debounced auto-save (triggers 1-2s after typing stops). Remove version conflict detection UI since CRDT collaboration (BL-050) handles conflicts natively. Subtle status indicator replaces the save button: "Saving...", "Saved", or "Save failed". Supersedes the old explicit save pattern. Prerequisite for real-time collaboration. Playbook backlog: PB-035.

### BL-050: Playbook Real-Time Collaboration (GDocs-style)
**Status**: Idea | **Effort**: L | **Spec**: —
**Depends on**: BL-049 | **Theme**: Outreach Engine

Full cursor presence and live document sync using Yjs + Hocuspocus (Tiptap's native CRDT stack). Multiple users editing the same playbook see each other's cursors, selections, and changes in real time. WebSocket sync server for document state. Backend persists CRDT document state (binary Yjs format), replacing the current `content` column approach. Supersedes the old version conflict detection pattern. Core product differentiator for collaborative GTM strategy work. Playbook backlog: PB-036.

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
**Status**: In Progress | **Effort**: S | **Spec**: —
**Depends on**: — | **Theme**: Contact Intelligence

Import contacts from LinkedIn "Download your data" archive (connections.csv format). Maps LinkedIn-specific fields (Connected On, Position, Company) to contact/company schema. Dedup by LinkedIn profile URL. Enables users to import their personal network as a lead source.

**Partial implementation via Browser Extension**: The Chrome extension (`feature/browser-extension`) now supports live lead extraction from Sales Navigator and LinkedIn activity monitoring. Extension imports use `POST /api/extension/leads` with LinkedIn URL dedup. The CSV archive import path remains to be built.

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

### BL-047: Voice Dialog Mode — Hands-Free GTM Workflow + AI Avatar
**Status**: Idea | **Effort**: XL | **Spec**: —
**Depends on**: BL-031, BL-035 | **Theme**: Outreach Engine

Voice-based interaction mode where the AI speaks to the user in their native language and guides them through the full GTM workflow (strategy → contact sourcing → campaign prep) via voice dialog. Designed for busy company owners who want to work while driving, commuting, or otherwise hands-free.

Key features:
- Voice input/output in user's native language (Czech, German, English, etc.)
- AI narrates what's happening: "I've found 12 companies matching your ICP in the DACH region. The top 3 are..."
- User makes key decisions by voice: "Focus on the manufacturing ones" / "Skip that one"
- Full workflow coverage: create strategy, source contacts, prepare outreach — all voice-guided
- Session continuity: pick up where you left off
- Async handoff: voice session creates actionable items that can be reviewed later on desktop

Use case: Company owner driving 2 hours wants to create a GTM strategy, source a contact list, and prepare everything for campaign launch by the time they arrive.

**Quality Bar: ChatGPT Advanced Voice Mode or better**
- Real-time, natural conversation — not text-to-speech bolted on
- Low latency (near-instant response, no awkward pauses)
- Interruption support (user can cut in, AI adapts)
- Natural prosody (varies tone, pace, emphasis — not monotone TTS)
- Multilingual fluency (switches between English/Czech/German naturally mid-conversation)
- Context awareness (remembers prior conversation, references past points)
- "Thinking out loud" narration ("Let me look at your contacts... okay, I see 3 that match...")
- Technology candidates: OpenAI Realtime API, ElevenLabs Conversational AI, or equivalent native voice-to-voice model
- Basic TTS/STT pipelines are NOT acceptable — this must feel like talking to a real person

**AI Avatar / Virtual Team Member** (expanded scope):
- Animated AI avatar with voice that serves as a virtual team member, not just a chatbot
- Creates sense of presence and accountability — "someone is working on this"
- Avatar narrates progress: "I'm analyzing your ICP now... found 3 strong segments"
- Expressive — shows thinking, excitement about good findings, concern about gaps
- Designed for AI-first founders who spend 8+ hours/day working with AI and need human-like interaction to avoid isolation
- Technologies to explore: ElevenLabs (voice), HeyGen/Synthesia (avatar), WebRTC (real-time), or lightweight animated character (lower cost)
- Could be a browser tab, mobile app, or even a desktop companion widget

This addresses the "lonely AI-first founder" use case — turning AI tools from text interfaces into virtual teammates with presence.

### BL-048: Continuous Learning Loop — AI That Gets Smarter With Every Interaction
**Status**: Idea | **Effort**: XL | **Spec**: —
**Depends on**: BL-047, BL-031, BL-035 | **Theme**: Intelligence Engine

Machine learning feedback loop where the AI strategist learns from every interaction and campaign outcome at both individual user and platform-wide levels. First customer gets a good strategist. Hundredth customer gets an exceptional one.

**User-Level Learning:**
- Track what approaches/angles/channels worked for this specific user's market and audience
- Remember past campaigns: "We tried approach X, reply rate was 2%. Approach Y got 8%."
- Adapt recommendations based on proven results: "For your DACH manufacturing prospects, ROI framing outperforms innovation framing 4:1"
- Learn buyer persona preferences: "Marketing Directors respond to case studies, CTOs respond to technical whitepapers"
- Build a feedback loop: strategy → outreach → results → refined strategy

**Cross-User Learning (Anonymized):**
- Aggregate anonymized performance data across all customers
- Surface platform-wide insights: "LinkedIn outperforms cold email 3:1 for German market"
- Best practices emerge from data, not assumptions: send times, message length, subject lines
- Industry-specific benchmarks: "SaaS companies targeting SMB see 12% reply rate average"
- Every customer's wins improve every other customer's recommendations

**Implementation Ideas:**
- Outcome tracking: link campaign results (reply rates, meetings booked, deals closed) back to strategy decisions
- Feedback ingestion: user marks what worked/didn't after campaign runs
- Model fine-tuning or RAG: inject proven patterns into system prompts
- A/B testing engine: automatically test variations and learn from results
- Benchmarking dashboard: show how user's metrics compare to anonymized platform averages

**Key Insight**: This is the moat. As the system learns from real outcomes across thousands of campaigns, recommendations become prescriptive and increasingly personalized — hard to replicate without the data.

## Won't Have (for now)

_No items yet._

## Completed

### BL-045: Entity Detail Cleanup (Done 2026-02-19)
**Status**: Done | **Effort**: M | **Spec**: `docs/specs/entity-detail-cleanup/`
Restructure CompanyDetail and ContactDetail views per enrichment field audit. Remove deprecated pipeline fields, surface all L2 enrichment modules, add stage_completions timeline, move scores and triage metadata to appropriate tabs.

### BL-001: Contacts & Companies Screens (Done 2026-02-13)
Dashboard screens with infinite scroll, virtual DOM windowing, filters, detail modals, inline editing. ADR-001.

### BL-002: L1 Workflow Postgres Migration (Done 2026-02-16)
Native Python L1 enrichment via Perplexity sonar API, replacing n8n webhook. 8 QC checks, research storage, review workflow, LinkedIn context. 105 enricher + 32 route tests. ADR-003, PR #1.

### BL-045: Vanilla JS Migration (Done 2026-02-19)
Eliminate all vanilla JS from the dashboard. Port Import page (3-step wizard, CSV + Google OAuth) and Admin page (namespace/user CRUD) to React. Delete 14 vanilla files (12K lines). Enhanced placeholders for Playbook, Echo, LLM Costs. Simplified deploy script. Spec: `docs/specs/vanilla-js-migration/`. Resolves TD-008.

### BL-046: Contact ICP Filters (Done 2026-02-19)
Faceted multi-value filtering on the Contacts page. 8 filter dimensions (industry, company_size, geo_region, revenue_range, seniority_level, department, job_titles, linkedin_activity), each with include/exclude toggle. Faceted count endpoint (`POST /api/contacts/filter-counts`), job title typeahead (`GET /api/contacts/job-titles`). Frontend: `MultiSelectFilter`, `JobTitleFilter`, `useAdvancedFilters` hook with URL serialization. Spec: `docs/specs/contact-icp-filters/`.

### BL-006: Contact List Import & Cleanup — Phase 1 (Done 2026-02-13)
CSV upload with AI column mapping, dedup preview, batch import. 80 unit tests. ADR-002.
