# Leadgen Pipeline — System Inventory

Generated: 2026-03-02
Branch: staging (commit 625753a)

---

## 1. Frontend Pages / Routes

The frontend is a React SPA (Vite + TypeScript) with namespace-scoped routing (`/:namespace/*`). Navigation is organized into four pillars: Playbook, Radar, Reach, Echo.

| Route | Page Component | Status |
|-------|---------------|--------|
| `/` | LoginPage | **BUILT** |
| `/:namespace` (index) | Redirects to `/contacts` | **BUILT** |
| `/:namespace/contacts` | ContactsPage | **BUILT** |
| `/:namespace/contacts/:contactId` | ContactDetailPage | **BUILT** |
| `/:namespace/companies` | CompaniesPage | **BUILT** |
| `/:namespace/companies/:companyId` | CompanyDetailPage | **BUILT** |
| `/:namespace/import` | ImportPage (3-step wizard) | **BUILT** |
| `/:namespace/enrich` | EnrichPage (DAG pipeline) | **BUILT** |
| `/:namespace/messages` | MessagesPage | **BUILT** |
| `/:namespace/campaigns` | CampaignsPage (list) | **BUILT** |
| `/:namespace/campaigns/:campaignId` | CampaignDetailPage (6 tabs) | **BUILT** |
| `/:namespace/campaigns/:campaignId/review` | MessageReviewPage | **BUILT** |
| `/:namespace/playbook` | PlaybookPage (split-view editor + AI chat) | **BUILT** |
| `/:namespace/playbook/:phase` | PlaybookPage (phase-specific) | **BUILT** |
| `/:namespace/echo` | PlaceholderPage ("Echo Analytics") | **PLACEHOLDER** |
| `/:namespace/admin` | AdminPage (namespaces + users + credits) | **BUILT** |
| `/:namespace/admin/tokens` | TokensPage (credit usage dashboard) | **BUILT** |
| `/:namespace/preferences` | PreferencesPage (4 tabs) | **BUILT** |
| `/:namespace/llm-costs` | LlmCostsPage (super_admin only) | **BUILT** |

**Navigation pillars:**
- **Playbook**: ICP Summary
- **Radar**: Contacts, Companies, Import, Enrich
- **Reach**: Campaigns
- **Echo**: Dashboard Demo (placeholder)

---

## 2. API Endpoints

### Auth (`/api/auth`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| POST | `/api/auth/login` | JWT login (email + password) | **BUILT** |
| POST | `/api/auth/refresh` | Refresh access token | **BUILT** |
| GET | `/api/auth/me` | Get current user info | **BUILT** |

### Health
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/health` | Health check | **BUILT** |

### Contacts (`/api/contacts`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/contacts` | List contacts with filters/pagination | **BUILT** |
| GET | `/api/contacts/:id` | Get contact detail with enrichment | **BUILT** |
| PATCH | `/api/contacts/:id` | Update contact fields | **BUILT** |
| POST | `/api/contacts/filter-counts` | Get filter facet counts | **BUILT** |
| GET | `/api/contacts/job-titles` | Get distinct job titles | **BUILT** |
| POST | `/api/contacts/search` | Full-text search contacts | **BUILT** |
| POST | `/api/contacts/search/summary` | Search with aggregated summary | **BUILT** |

### Companies (`/api/companies`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/companies` | List companies with filters/pagination | **BUILT** |
| POST | `/api/companies/filter-counts` | Filter facet counts | **BUILT** |
| GET | `/api/companies/:id` | Get company detail + enrichment + contacts | **BUILT** |
| PATCH | `/api/companies/:id` | Update company fields | **BUILT** |
| POST | `/api/companies/:id/enrich-registry` | Trigger ARES/registry enrichment | **BUILT** |
| POST | `/api/companies/:id/confirm-registry` | Confirm registry data | **BUILT** |

### Import (`/api/imports`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| POST | `/api/imports/upload` | Upload CSV file for import | **BUILT** |
| POST | `/api/imports/:jobId/remap` | Re-map columns | **BUILT** |
| POST | `/api/imports/:jobId/preview` | Preview import results | **BUILT** |
| POST | `/api/imports/:jobId/execute` | Execute the import | **BUILT** |
| GET | `/api/imports/:jobId/results` | Get import results | **BUILT** |
| GET | `/api/imports/:jobId/status` | Get import status | **BUILT** |
| GET | `/api/imports` | List past imports | **BUILT** |

### Enrichment (`/api/enrich`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| POST | `/api/enrich/estimate` | Estimate enrichment cost | **BUILT** |
| POST | `/api/enrich/start` | Start enrichment run | **BUILT** |
| GET | `/api/enrich/review` | Get items needing QC review | **BUILT** |
| POST | `/api/enrich/resolve` | Resolve QC review item | **BUILT** |

### Enrichment Config (`/api/enrichment-configs`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| POST | `/api/enrichment-configs` | Create config preset | **BUILT** |
| GET | `/api/enrichment-configs` | List config presets | **BUILT** |
| GET | `/api/enrichment-configs/:id` | Get config detail | **BUILT** |
| PATCH | `/api/enrichment-configs/:id` | Update config | **BUILT** |
| DELETE | `/api/enrichment-configs/:id` | Delete config | **BUILT** |
| POST | `/api/enrichment-schedules` | Create schedule | **BUILT** |
| GET | `/api/enrichment-schedules` | List schedules | **BUILT** |
| PATCH | `/api/enrichment-schedules/:id` | Update schedule | **BUILT** |
| DELETE | `/api/enrichment-schedules/:id` | Delete schedule | **BUILT** |

### Pipeline (`/api/pipeline`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| POST | `/api/pipeline/start` | Start a single enrichment stage | **BUILT** |
| POST | `/api/pipeline/stop` | Stop a running stage | **BUILT** |
| GET | `/api/pipeline/status` | Get pipeline + stage run status | **BUILT** |
| POST | `/api/pipeline/run-all` | Run all selected stages (full DAG) | **BUILT** |
| POST | `/api/pipeline/stop-all` | Stop all running stages | **BUILT** |
| POST | `/api/pipeline/dag-run` | Start DAG-based pipeline execution | **BUILT** |
| GET | `/api/pipeline/dag-status` | Get DAG execution status | **BUILT** |
| POST | `/api/pipeline/dag-stop` | Stop DAG execution | **BUILT** |

### Messages (`/api/messages`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/messages` | List messages with filters | **BUILT** |
| PATCH | `/api/messages/:id` | Update message (status, body, subject) | **BUILT** |
| GET | `/api/messages/:id/regenerate/estimate` | Estimate regeneration cost | **BUILT** |
| POST | `/api/messages/:id/regenerate` | Regenerate a message via LLM | **BUILT** |
| PATCH | `/api/messages/batch` | Batch update messages | **BUILT** |

### Campaigns (`/api/campaigns`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/campaigns` | List campaigns | **BUILT** |
| POST | `/api/campaigns` | Create campaign | **BUILT** |
| GET | `/api/campaigns/:id` | Get campaign detail | **BUILT** |
| PATCH | `/api/campaigns/:id` | Update campaign | **BUILT** |
| DELETE | `/api/campaigns/:id` | Delete campaign | **BUILT** |
| POST | `/api/campaigns/:id/clone` | Clone a campaign | **BUILT** |
| GET | `/api/campaign-templates` | List campaign templates | **BUILT** |
| POST | `/api/campaign-templates` | Create campaign template | **BUILT** |
| POST | `/api/campaigns/:id/save-as-template` | Save campaign as template | **BUILT** |
| PATCH | `/api/campaign-templates/:id` | Update template | **BUILT** |
| DELETE | `/api/campaign-templates/:id` | Delete template | **BUILT** |
| GET | `/api/campaigns/:id/contacts` | List campaign contacts | **BUILT** |
| POST | `/api/campaigns/:id/contacts` | Add contacts to campaign | **BUILT** |
| DELETE | `/api/campaigns/:id/contacts` | Remove contacts from campaign | **BUILT** |
| POST | `/api/campaigns/:id/enrichment-check` | Check contact enrichment readiness | **BUILT** |
| POST | `/api/campaigns/:id/cost-estimate` | Estimate generation cost | **BUILT** |
| POST | `/api/campaigns/:id/generate` | Start message generation (background) | **BUILT** |
| GET | `/api/campaigns/:id/generation-status` | Poll generation progress | **BUILT** |
| DELETE | `/api/campaigns/:id/generate` | Cancel generation | **BUILT** |
| POST | `/api/campaigns/:id/disqualify-contact` | Disqualify a contact | **BUILT** |
| GET | `/api/campaigns/:id/review-summary` | Get review approval stats | **BUILT** |
| GET | `/api/campaigns/:id/review-queue` | Get review queue for messages | **BUILT** |
| PATCH | `/api/campaigns/:id/messages/:msgId` | Update individual campaign message | **BUILT** |
| POST | `/api/campaigns/:id/send-emails` | Send emails via Resend | **BUILT** |
| GET | `/api/campaigns/:id/send-status` | Check email send status | **BUILT** |
| POST | `/api/campaigns/:id/queue-linkedin` | Queue LinkedIn messages | **BUILT** |
| GET | `/api/campaigns/:id/analytics` | Get campaign analytics | **BUILT** |
| GET | `/api/campaigns/:id/messages/export-csv` | Export messages as CSV | **BUILT** |
| POST | `/api/campaigns/:id/conflict-check` | Check contact overlap conflicts | **BUILT** |
| POST | `/api/campaigns/:id/messages/batch` | Batch update campaign messages | **BUILT** |

### Playbook (`/api/playbook`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/playbook` | Get playbook strategy document | **BUILT** |
| PUT | `/api/playbook` | Save playbook document | **BUILT** |
| POST | `/api/playbook/undo` | Undo AI edit (restore version) | **BUILT** |
| PUT | `/api/playbook/phase` | Advance/set playbook phase | **BUILT** |
| POST | `/api/playbook/extract` | Extract ICP data from strategy | **BUILT** |
| GET | `/api/playbook/contacts` | Get ICP-matching contacts | **BUILT** |
| POST | `/api/playbook/contacts/confirm` | Confirm contact selection | **BUILT** |
| POST | `/api/playbook/research` | Trigger background research | **BUILT** |
| GET | `/api/playbook/research` | Get research status | **BUILT** |
| GET | `/api/playbook/chat` | Get chat history (SSE-streamable) | **BUILT** |
| POST | `/api/playbook/chat/new-thread` | Start new chat thread | **BUILT** |
| POST | `/api/playbook/chat` | Send chat message (SSE streaming) | **BUILT** |
| POST | `/api/playbook/:id/messages/setup` | Configure message generation | **BUILT** |
| POST | `/api/playbook/:id/generate-messages` | Generate messages for playbook | **BUILT** |
| GET | `/api/playbook/:id/messages` | Get generated messages | **BUILT** |
| PATCH | `/api/playbook/:id/messages/:msgId` | Update a playbook message | **BUILT** |
| POST | `/api/playbook/:id/messages/batch` | Batch update messages | **BUILT** |
| POST | `/api/playbook/:id/confirm-messages` | Confirm messages for campaign | **BUILT** |

### Strategy Templates (`/api/strategy-templates`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/strategy-templates` | List strategy templates | **BUILT** |
| GET | `/api/strategy-templates/:id` | Get template detail | **BUILT** |
| POST | `/api/strategy-templates` | Create template | **BUILT** |
| PATCH | `/api/strategy-templates/:id` | Update template | **BUILT** |
| DELETE | `/api/strategy-templates/:id` | Delete template | **BUILT** |
| POST | `/api/playbook/apply-template` | Apply strategy template to playbook | **BUILT** |

### Tags (`/api/tags`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/tags` | List tags | **BUILT** |
| POST | `/api/tags` | Create tag | **BUILT** |
| POST | `/api/tag-stats` | Get tag statistics | **BUILT** |

### Bulk Operations (`/api/bulk`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| POST | `/api/bulk/add-tags` | Bulk add tags to contacts/companies | **BUILT** |
| POST | `/api/bulk/remove-tags` | Bulk remove tags | **BUILT** |
| POST | `/api/bulk/assign-campaign` | Bulk assign contacts to campaign | **BUILT** |
| POST | `/api/contacts/matching-count` | Count matching contacts for filter | **BUILT** |
| POST | `/api/companies/matching-count` | Count matching companies for filter | **BUILT** |

### Tenants (`/api/tenants`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/tenants` | List tenants | **BUILT** |
| POST | `/api/tenants` | Create tenant (namespace) | **BUILT** |
| GET | `/api/tenants/:id` | Get tenant detail | **BUILT** |
| PUT | `/api/tenants/:id` | Update tenant | **BUILT** |
| DELETE | `/api/tenants/:id` | Delete tenant | **BUILT** |
| PATCH | `/api/tenants/:id/settings` | Update tenant settings | **BUILT** |
| GET | `/api/tenants/:id/users` | Get tenant users | **BUILT** |
| GET | `/api/tenants/onboarding-status` | Get onboarding milestones | **BUILT** |
| PATCH | `/api/tenants/onboarding-settings` | Update onboarding prefs | **BUILT** |

### Users (`/api/users`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/users` | List users | **BUILT** |
| POST | `/api/users` | Create user | **BUILT** |
| PUT | `/api/users/:id` | Update user | **BUILT** |
| DELETE | `/api/users/:id` | Delete user | **BUILT** |
| PUT | `/api/users/:id/password` | Change password | **BUILT** |
| DELETE | `/api/users/:id/roles/:tenantId` | Remove role from user | **BUILT** |

### Token Budget (`/api/admin/tokens`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/admin/tokens` | Get token dashboard (usage by op/user) | **BUILT** |
| GET | `/api/admin/tokens/status` | Get budget status | **BUILT** |
| GET | `/api/admin/tokens/history` | Usage history over time | **BUILT** |
| PUT | `/api/admin/tokens/budget` | Set token budget | **BUILT** |
| POST | `/api/admin/tokens/topup` | Top up token balance | **BUILT** |
| GET | `/api/admin/tokens/cost-breakdown` | Super-admin cost breakdown | **BUILT** |

### LLM Usage (`/api/llm-usage`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/llm-usage/summary` | Aggregated LLM usage (super_admin) | **BUILT** |
| GET | `/api/llm-usage/logs` | Raw LLM usage logs | **BUILT** |

### Custom Fields (`/api/custom-fields`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/custom-fields` | List custom field definitions | **BUILT** |
| POST | `/api/custom-fields` | Create custom field | **BUILT** |
| PUT | `/api/custom-fields/:id` | Update custom field | **BUILT** |
| DELETE | `/api/custom-fields/:id` | Delete custom field | **BUILT** |

### OAuth (`/api/oauth`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/oauth/google/auth-url` | Get Google OAuth URL | **BUILT** |
| GET | `/api/oauth/google/callback` | Handle OAuth callback | **BUILT** |
| GET | `/api/oauth/connections` | List OAuth connections | **BUILT** |
| DELETE | `/api/oauth/connections/:id` | Revoke OAuth connection | **BUILT** |

### Gmail (`/api/gmail`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| POST | `/api/gmail/contacts/fetch` | Fetch contacts from Gmail | **BUILT** |
| POST | `/api/gmail/contacts/:jobId/preview` | Preview Gmail contacts | **BUILT** |
| POST | `/api/gmail/contacts/:jobId/execute` | Import Gmail contacts | **BUILT** |
| POST | `/api/gmail/scan/start` | Start Gmail reply scan | **BUILT** |
| GET | `/api/gmail/scan/:jobId/status` | Check scan status | **BUILT** |

### Chrome Extension (`/api/extension`)
| Method | Path | Description | Status |
|--------|------|-------------|--------|
| POST | `/api/extension/leads` | Submit leads from extension | **BUILT** |
| POST | `/api/extension/activities` | Submit activities from extension | **BUILT** |
| GET | `/api/extension/status` | Get extension connection status | **BUILT** |
| GET | `/api/extension/linkedin-queue` | Get LinkedIn action queue | **BUILT** |
| PATCH | `/api/extension/linkedin-queue/:id` | Update queue item status | **BUILT** |
| GET | `/api/extension/linkedin-queue/stats` | Queue statistics | **BUILT** |

---

## 3. Chat / AI Features

### Status: **BUILT**

**Architecture**: App-level ChatProvider wraps the entire app. Uses SSE streaming (POST-based, not EventSource) for real-time AI responses.

**Components:**
- `ChatPanel` — Sliding right-side panel for app-wide AI chat. Does NOT render on Playbook page (uses inline chat instead). Responsive: 400px desktop, 320px tablet, full-screen mobile.
- `ChatProvider` — App-level context managing: messages, streaming text, open/closed state, tool call state, page context awareness, analysis suggestions.
- `ChatInput` — Text input with Cmd+K keyboard shortcut.
- `ChatMessages` — Message rendering with markdown support.
- `ChatMermaidBlock` — Mermaid diagram rendering in chat.
- `ChatFilterSyncBar` — ICP filter sync from chat to contacts page.
- `PlaybookChat` — Inline chat specifically for the Playbook page.

**Backend AI agent:**
- `agent_executor.py` — Full agentic tool-use loop via Claude API. Max 10 tool iterations per turn. Rate-limited (3 web_search/turn, 5 default).
- SSE events: `tool_start`, `tool_result`, `chunk` (streaming text), `done`, `analysis_done`.
- `playbook_service.py` — System prompt builder positioning AI as GTM strategy consultant. Includes enrichment data, company research, strategy document in context.

**Registered AI Tools (6 categories, registered at app startup):**
1. **Strategy tools** (`strategy_tools.py`): Read/write strategy document sections, extract ICP data, manage extracted_data fields. Version-controlled with undo support.
2. **Analyze tools** (`analyze_tools.py`): `count_contacts`, `count_companies`, `list_contacts`, `list_companies` — tenant-isolated CRM queries.
3. **Search tools** (`search_tools.py`): `web_search` — Perplexity sonar API integration with cost logging and citation extraction.
4. **Campaign tools** (`campaign_tools.py`): `filter_contacts`, `create_campaign`, `assign_to_campaign`, `check_strategy_conflicts`, `get_campaign_summary`.
5. **ICP filter tools** (`icp_filter_tools.py`): `apply_icp_filters` — Maps ICP criteria to contact filter parameters with match counts.
6. **Enrichment gap tools** (`enrichment_gap_tools.py`): `get_enrichment_gaps` — Cross-references ICP criteria with entity_stage_completions.

**Key features:**
- Tool call visualization in UI (ThinkingIndicator, ToolCallCard)
- Document change detection (AI edits trigger refresh + undo)
- Persistent chat history across page navigation
- Proactive analysis with dynamic suggestion chips
- New thread creation

---

## 4. Import Features

### Status: **BUILT**

**Frontend**: 3-step wizard (Upload, Map Columns, Preview & Import) + Past Imports history.

**Supported sources:**
- **CSV upload**: File upload with automatic column detection
- **Google Contacts**: OAuth-based Google integration (via `/api/oauth/google/auth-url` and callback)

**Import flow:**
1. Upload CSV or connect Google account
2. Map source columns to system fields (first_name, last_name, email, company, etc.)
3. Preview results with dedup strategy (skip / update / create_new)
4. Execute import with batch naming and owner assignment

**Backend services:**
- `csv_mapper.py` — CSV parsing and column mapping
- `google_contacts.py` — Google People API integration
- `google_oauth.py` — OAuth2 token management
- `dedup.py` — Deduplication logic

**Custom fields**: Support for defining and mapping custom fields during import.

---

## 5. GTM Strategy / Playbook Features

### Status: **BUILT**

**Multi-phase playbook workflow:**
1. **Strategy** (Phase 1): AI-assisted ICP strategy editing. Split-view: markdown editor (left 60%) + AI chat (right 40%). Auto-save with debounce. Sections: Executive Summary, ICP, Buyer Personas, Value Proposition, Competitive Positioning, Channel Strategy, Messaging Framework, Metrics & KPIs, 90-Day Action Plan.
2. **Contacts** (Phase 2): ICP-to-filter mapping (`ContactsPhasePanel`). AI extracts ICP criteria and maps to contact filters. Shows matching contacts with confirmation flow.
3. **Messages** (Phase 3): Message generation for selected contacts (`MessagesPhasePanel`). Multi-step outreach sequence configuration.
4. **Campaign** (Phase 4): Campaign creation from playbook flow (connects to Campaigns feature).

**Key components:**
- `PhaseIndicator` — Horizontal stepper (4 phases, all always navigable)
- `StrategyEditor` — Rich text editor for strategy document
- `PlaybookOnboarding` — First-time visitor flow
- `TemplateSelector` — Apply strategy templates
- `PhasePanel` — Phase-specific content panels

**Backend:**
- `StrategyDocument` model — JSONB content, extracted_data, versioned
- `StrategyVersion` model — Snapshot history with undo support
- `StrategyChatMessage` model — Persistent chat history per playbook
- Strategy extraction: Converts markdown strategy into structured ICP data
- Research: Background research trigger for enrichment data collection

**Strategy templates:**
- Create, edit, delete strategy templates
- Apply templates to new playbooks
- Templates stored in `StrategyTemplate` model with sections + extracted_data

---

## 6. Enrichment Pipeline

### Status: **BUILT**

**Frontend**: DAG-based enrichment configuration with visual pipeline.

**Components:**
- `EnrichPage` — Main enrichment page with DAG visualization
- `DagVisualization` — Visual stage layout
- `DagEdges` — SVG edge connections between stages
- `DagControls` — Run/Stop controls
- `StageCard` — Individual stage cards with progress
- `SchedulePanel` — Schedule enrichment runs
- `CompletionPanel` — Run completion summary
- `ConfigManager` — Save/load enrichment config presets

**Enrichment stages (from `stage_registry.py`):**
| Stage | Entity | Dependencies | Mode | Cost |
|-------|--------|-------------|------|------|
| `l1` | Company | None | Native (Perplexity) | $0.02 |
| `l2` | Company | triage | Webhook (n8n) | $0.08 |
| `signals` | Company | l1 | Native | $0.05 |
| `registry` | Company | l1 | Native (ARES/BRreg/PRH) | $0.00 |
| `triage` | Company | l1 | Rules-based | $0.00 |
| `person` | Contact | l2 | Webhook/Native | varies |
| `profile` | Company | l1 | Native | varies |
| `market` | Company | l1 | Native | varies |
| `opportunity` | Company | l2 | Native | varies |

**Backend enrichment services:**
- `l1_enricher.py` — L1 Company Profile via Perplexity sonar. Includes domain resolution, QC checks.
- `l2_enricher.py` — L2 Deep Research (extended company analysis)
- `person_enricher.py` — Person-level enrichment
- `triage_evaluator.py` — Rules-based triage (tier/industry/geo/revenue filters). Zero cost.
- `qc_checker.py` — Quality control checks
- `dag_executor.py` — DAG-based pipeline executor. Entity-level completion tracking. Threaded background execution.
- `stage_registry.py` — Stage configuration (deps, entity types, country gates)
- `registries/` — Country-specific registries: ARES (CZ), BRreg (NO), PRH (FI), Recherche (FR), ISIR (CZ insolvency)

**Pipeline execution features:**
- DAG-based execution with dependency resolution
- Topological sorting for execution order
- Configurable soft dependencies (optional stages)
- Re-enrichment with freshness thresholds
- Sample size limiting
- Entity-level completion tracking (`EntityStageCompletion` model)
- Cost estimation before run
- Real-time progress polling

---

## 7. Message Generation

### Status: **BUILT**

**Generation engine** (`message_generator.py`):
- Uses Claude Haiku (claude-haiku-3-5-20241022) for message generation
- Background thread execution with progress tracking
- Configurable template steps (multi-step outreach sequences)
- Per-message cost estimation (input/output token estimates)
- Cost logging via `LlmUsageLog`

**Generation prompts** (`generation_prompts.py`):
- System prompt for message generation
- Channel-specific constraints (LinkedIn, email, call script)
- Prompt building with company/contact enrichment context

**Message types / channels:**
- `linkedin_connect` — LinkedIn connection request
- `linkedin_message` — LinkedIn InMail/message
- `email` — Email outreach
- `call_script` — Phone call script

**Message lifecycle:**
1. Configure template steps in campaign
2. Cost estimate before generation
3. Background generation (pollable status)
4. Review queue with approve/reject/edit
5. Regeneration (single message, with cost estimate)
6. Batch approve/reject
7. Export to CSV

**Message review features:**
- `MessageReviewPage` — Dedicated review queue page
- `EditPanel` — Inline message editing
- `RegenerationDialog` — Regenerate with feedback
- `DisqualifyDialog` — Disqualify contact from campaign
- Review summary stats (approved/rejected/pending counts)

---

## 8. Qualification / Scoring

### Status: **BUILT**

**Tier system** (assigned during L1 enrichment):
- Tier 1 - Platinum
- Tier 2 - Gold
- Tier 3 - Silver
- (additional tiers defined in data)

**Triage evaluation** (`triage_evaluator.py`):
- Rules-based company filtering post-L1
- Configurable rules: tier allowlist/blocklist, industry allowlist/blocklist, geo allowlist, min revenue, min employees, require B2B, max QC flags
- Zero-cost gate stage (no API calls)
- Output: pass/fail with reasons

**ICP scoring** (via playbook extraction):
- AI extracts ICP criteria from strategy document
- Criteria mapped to contact filters (industry, geography, company size, seniority)
- Match counting for filter combinations

**Contact qualification in campaigns:**
- Enrichment readiness check (`/api/campaigns/:id/enrichment-check`)
- Disqualification flow (`/api/campaigns/:id/disqualify-contact`)
- Contact conflict detection across campaigns

**Company status flow:**
New -> Triage: Passed / Triage: Review / Disqualified -> Enriched L2 / Enrichment Failed

---

## 9. Namespace / Tenant Management

### Status: **BUILT**

**Multi-tenant architecture:**
- Shared PostgreSQL schema with `tenant_id` column isolation
- Namespace URL routing: `leadgen.visionvolve.com/{namespace-slug}/page`
- JWT auth with `X-Namespace` header for tenant resolution

**Admin features:**
- `AdminPage` — Manage namespaces, users, roles, credits
- `NamespacesCard` — Create namespaces (super_admin only)
- `UsersCard` — User management with role assignment
- `AddUserModal` — Create new users
- `CreateNamespaceModal` — Create new namespaces

**API capabilities:**
- Full CRUD on tenants (create, read, update, delete)
- Tenant settings management
- User-tenant role assignments (viewer, editor, admin, super_admin)
- Per-tenant onboarding status tracking
- Per-tenant token budgets

---

## 10. Onboarding

### Status: **BUILT**

**Components:**
- `EntrySignpost` — Full-page welcome for empty namespaces. Three paths: Build a Strategy, Import Contacts, Browse Templates.
- `ProgressChecklist` — Lightweight progress widget. Auto-completing milestones: strategy saved, contacts imported, campaign created. Dismissible.
- `SmartEmptyState` — Context-aware empty states per page (CampaignsEmptyState, etc.)

**Backend:**
- Onboarding status API (`/api/tenants/onboarding-status`)
- Settings persistence (`/api/tenants/onboarding-settings`)
- Path selection persisted to tenant settings

---

## 11. Email Sending

### Status: **BUILT**

**Resend integration** (`send_service.py`):
- Send campaign emails via Resend API
- Idempotent send tracking via `EmailSendLog` model
- Rate limiting (100ms between sends, 10 req/s)
- Campaign-level sender config (from_email, from_name, reply_to)
- Per-message send status tracking

**API endpoints:**
- `POST /api/campaigns/:id/send-emails` — Trigger email send
- `GET /api/campaigns/:id/send-status` — Check send status

---

## 12. LinkedIn Integration

### Status: **BUILT** (via Chrome Extension)

**Chrome extension endpoints** (`extension_routes.py`):
- Submit leads from LinkedIn
- Submit activities (messages, events)
- LinkedIn action queue (connect, message)
- Queue status tracking

**Campaign LinkedIn features:**
- `POST /api/campaigns/:id/queue-linkedin` — Queue LinkedIn messages for extension pickup
- `LinkedInSendQueue` model — Queue management

---

## 13. Gmail Integration

### Status: **BUILT**

- Google OAuth connection (`/api/oauth/google/auth-url`, callback)
- Gmail contact import (fetch, preview, execute)
- Gmail reply scanning (detect responses to outreach)
- `GoogleConnect` component for OAuth flow in Import page

---

## 14. Campaign Analytics

### Status: **BUILT**

- `CampaignAnalytics` component
- `GET /api/campaigns/:id/analytics` — Detailed analytics endpoint
- Available as tab in CampaignDetailPage
- Tracks: messages generated, approved, sent, opens, replies, conversions

---

## 15. Preferences / Settings

### Status: **BUILT**

Four settings sections:
1. **General** — General namespace settings
2. **Language** — Language preferences for message generation
3. **Campaign Templates** — Manage campaign outreach templates
4. **Strategy Templates** — Manage strategy document templates

---

## 16. Token / Credit System

### Status: **BUILT**

- `NamespaceTokenBudget` model — Per-namespace credit allocation
- Credits dashboard (`TokensPage`) — Usage by operation, by user, over time
- Budget management: set budget, top-up, enforcement modes
- Alert thresholds and reset periods
- All user-facing displays in credits (never raw USD)
- Super-admin LLM cost dashboard (`LlmCostsPage`) shows raw USD

---

## 17. Outreach Approval & Sending

### Status: **BUILT**

**Campaign detail tabs (6):**
1. Contacts — Add/remove contacts, enrichment check
2. Generation — Configure template, estimate cost, generate messages
3. Review — Review queue with approve/reject/edit per message
4. Outreach — Send emails via Resend, queue LinkedIn messages. Approval dialog.
5. Analytics — Campaign performance metrics
6. Settings — Campaign config, sender settings, clone, save as template

**Outreach approval flow:**
- Review summary shows approval stats
- `OutreachApprovalDialog` for final send confirmation
- Email sending via Resend
- LinkedIn queuing for Chrome extension

---

## 18. Echo Analytics

### Status: **PLACEHOLDER**

- Route exists (`/:namespace/echo`)
- Shows a `PlaceholderPage` with description: "Outreach performance dashboard -- conversion funnels, response rates by channel, pipeline velocity."
- No implementation yet

---

## 19. Data Model Summary

**46 SQLAlchemy models** covering:
- Core: User, Tenant, UserTenantRole, Owner
- CRM: Contact, Company, Tag, ContactTagAssignment, CompanyTagAssignment, CompanyTag
- Enrichment: CompanyEnrichmentL1, CompanyEnrichmentL2, CompanyEnrichmentProfile, CompanyEnrichmentSignals, CompanyEnrichmentMarket, CompanyEnrichmentOpportunity, ContactEnrichment
- Registry: CompanyRegistryData, CompanyInsolvencyData, CompanyLegalProfile
- Pipeline: StageRun, PipelineRun, EntityStageCompletion, EnrichmentConfig, EnrichmentSchedule
- Import: ImportJob, CustomFieldDefinition
- Messages: Message, Campaign, CampaignContact, CampaignTemplate, CampaignOverlapLog
- Sending: EmailSendLog, LinkedInSendQueue
- Strategy: StrategyDocument, StrategyChatMessage, StrategyVersion, StrategyTemplate
- AI: ToolExecution, PlaybookLog
- Costs: LlmUsageLog, NamespaceTokenBudget
- OAuth: OAuthConnection
- Activity: Activity, ResearchAsset

---

## 20. Summary Matrix

| Feature Area | Status | Notes |
|-------------|--------|-------|
| Auth & Login | **BUILT** | JWT with refresh tokens, bcrypt passwords |
| Contacts CRUD | **BUILT** | Full listing, detail, search, filtering |
| Companies CRUD | **BUILT** | Full listing, detail, enrichment timeline |
| CSV Import | **BUILT** | 3-step wizard with column mapping |
| Google Import | **BUILT** | OAuth + People API integration |
| Enrichment Pipeline | **BUILT** | DAG executor with 9+ stages, native + webhook |
| L1 Enrichment | **BUILT** | Native Perplexity integration |
| L2 Enrichment | **BUILT** | Webhook to n8n (or native) |
| Triage/Qualification | **BUILT** | Rules-based, configurable |
| Registry Enrichment | **BUILT** | ARES (CZ), BRreg (NO), PRH (FI), Recherche (FR) |
| Playbook (Strategy) | **BUILT** | AI-assisted ICP strategy editor |
| Playbook (Contacts) | **BUILT** | ICP-to-filter mapping |
| Playbook (Messages) | **BUILT** | Message generation from playbook |
| Playbook (Campaign) | **BUILT** | Campaign creation from playbook |
| AI Chat (app-wide) | **BUILT** | Sliding panel with SSE streaming |
| AI Chat (playbook) | **BUILT** | Inline split-view with tool use |
| AI Agent Tools | **BUILT** | 6 tool categories (strategy, analyze, search, campaign, ICP filter, enrichment gap) |
| Web Search (AI) | **BUILT** | Perplexity sonar integration |
| Message Generation | **BUILT** | Claude Haiku, multi-channel templates |
| Message Review | **BUILT** | Queue with approve/reject/edit/regenerate |
| Campaigns | **BUILT** | Full lifecycle: create, contacts, generate, review, send |
| Campaign Templates | **BUILT** | Save/apply campaign templates |
| Strategy Templates | **BUILT** | Save/apply strategy templates |
| Email Sending | **BUILT** | Resend API with tracking |
| LinkedIn Queue | **BUILT** | Chrome extension integration |
| Gmail Scan | **BUILT** | Reply detection |
| Namespace Management | **BUILT** | Multi-tenant with URL routing |
| User Management | **BUILT** | CRUD, roles, password management |
| Token/Credit System | **BUILT** | Budget, usage tracking, enforcement |
| LLM Cost Dashboard | **BUILT** | Super-admin USD breakdown |
| Onboarding | **BUILT** | Entry signpost + progress checklist |
| Preferences | **BUILT** | General, language, templates |
| Custom Fields | **BUILT** | Define and use custom fields |
| Bulk Operations | **BUILT** | Bulk tag, bulk campaign assign |
| Echo Analytics | **PLACEHOLDER** | Route exists, no implementation |
| Chrome Extension API | **BUILT** | Leads, activities, LinkedIn queue |
| Campaign Analytics | **BUILT** | Per-campaign performance metrics |
| CSV Export | **BUILT** | Campaign messages export |
