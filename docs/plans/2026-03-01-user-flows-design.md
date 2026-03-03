# Strategic User Flows (JTBD)

> Internal reference for agents and developers. Each flow maps a user job from entry point to value realized, with screens, APIs, state changes, and cross-flow connections.

## How to Read This Document

- **Job Statement**: JTBD format — situation → action → outcome
- **Status**: Built (fully functional) | Partial (core works, gaps listed) | Planned (not yet implemented)
- **Steps**: Sequential with screen path, API endpoint, and data state change
- **Cross-Flow**: How this flow feeds into or receives from other flows

---

## FLOW-1: Build GTM Strategy From Scratch

**Job Statement**: When I'm starting outbound for my company and have no documented strategy, I want the AI to research my company and generate a structured GTM playbook, so I can have a professional strategy in minutes instead of weeks.

**Persona**: Founder / Head of Sales at a 5-50 person company
**Entry Point**: `/{namespace}/playbook` (Playbook pillar)
**Value Moment**: Complete 8-section strategy document with extractable ICP criteria that drive downstream contact filtering
**Status**: Built

**Steps**:
1. **Navigate to Playbook** — User clicks Playbook in top nav
   - Screen: `/{namespace}/playbook`
   - API: `GET /api/playbook` (loads existing or empty state)
   - State: Playbook document loaded or initialized

2. **Trigger self-company research** — User enters company domain + objective, clicks Research
   - Screen: `/{namespace}/playbook` (research panel)
   - API: `POST /api/playbook/research` → triggers L1+L2 enrichment on user's own company
   - State: Research job queued, background enrichment running

3. **AI generates initial playbook** — System uses research results + objective to seed 8 sections (ICP, Personas, Channels, Messaging, Positioning, Differentiation, Campaigns, Execution)
   - Screen: `/{namespace}/playbook` (editor populates)
   - API: `PUT /api/playbook` (auto-save)
   - State: Playbook content created with AI-generated sections

4. **Refine via AI chat** — User asks chat to adjust sections ("Make ICP more specific to healthcare SaaS")
   - Screen: `/{namespace}/playbook` (right sidebar chat)
   - API: `POST /api/playbook/chat` → AI reads doc context, suggests edits
   - State: Chat history persisted, playbook sections updated

5. **Progress through phases** — User validates each phase via stepper (ICP → Personas → Channels → etc.)
   - Screen: `/{namespace}/playbook/{phase}`
   - API: `PUT /api/playbook/phase` (marks phase complete)
   - State: Phase status updated, structured data extracted

6. **Extract structured ICP criteria** — System extracts ICP as structured JSON for downstream use
   - API: `POST /api/playbook/extract`
   - State: ICP criteria (industry, size, geo, seniority, etc.) stored as filterable attributes

**Cross-Flow Connections**:
- **Feeds into**: FLOW-4 (ICP criteria drive contact filtering), FLOW-5 (messaging angles drive message generation)
- **Receives from**: FLOW-8 (campaign results suggest strategy adjustments)

**Gaps**:
- Strategy scoring (BL-058) is spec'd but not fully deployed
- Conflict detection between strategy sections is spec'd but not fully deployed
- Phase extraction needs validation that criteria map cleanly to contact filter facets

---

## FLOW-2: Import and Clean a Contact List

**Job Statement**: When I have a CSV/XLSX of contacts from an event, purchase, or scrape, I want to upload it and have the system auto-map columns, deduplicate, and clean the data, so I can start working with contacts immediately without manual data wrangling.

**Persona**: Founder / Sales Ops
**Entry Point**: `/{namespace}/import` (Radar → Import)
**Value Moment**: Contacts in PostgreSQL with correct field mapping, duplicates resolved, ready for enrichment
**Status**: Built

**Steps**:
1. **Upload file** — Drag-and-drop CSV/XLSX
   - Screen: `/{namespace}/import`
   - API: `POST /api/imports/upload`
   - State: File parsed, import job created with job_id

2. **AI column mapping** — System auto-detects which CSV columns map to contact fields (name, email, company, title, etc.)
   - Screen: `/{namespace}/import` (mapping preview)
   - API: `POST /api/imports/{job_id}/remap` (if user adjusts mapping)
   - State: Column mapping stored on import job

3. **Preview with dedup** — System shows preview rows with deduplication decisions (create/merge/skip)
   - Screen: `/{namespace}/import` (preview table)
   - API: `POST /api/imports/{job_id}/preview`
   - State: Row-level decisions shown (matches against existing contacts)

4. **Execute import** — User confirms, system processes all rows
   - API: `POST /api/imports/{job_id}/execute`
   - State: Contacts created/merged in PostgreSQL, import results stored

5. **Review results** — Summary of imported/merged/skipped counts
   - API: `GET /api/imports/{job_id}/results`
   - State: Import complete, contacts available in contact list

**Cross-Flow Connections**:
- **Feeds into**: FLOW-3 (new contacts need enrichment), FLOW-4 (contacts available for filtering)
- **Receives from**: None (this is a primary entry point)

**Gaps**:
- Google Contacts OAuth import is built but could be more prominent
- Gmail signature scanner exists but is separate from main import flow
- No LinkedIn CSV import template

---

## FLOW-3: Enrich Contacts With Market Intelligence

**Job Statement**: When I have raw contacts with just name/email/company, I want the system to automatically research each company and person, so I can see company tier, funding signals, hiring patterns, and person role fit without manual research.

**Persona**: Founder / Sales Ops
**Entry Point**: `/{namespace}/enrich` (Radar → Enrich)
**Value Moment**: Contacts enriched with multi-level intelligence (L1 company basics → triage → L2 deep company → person data)
**Status**: Built

**Steps**:
1. **View batch list** — See all enrichment batches with status
   - Screen: `/{namespace}/enrich`
   - API: `GET /api/pipeline/batches`
   - State: Batch list loaded

2. **Trigger enrichment** — Select batch/contacts, configure pipeline (skip L1/L2/Person toggles)
   - Screen: `/{namespace}/enrich` (trigger form)
   - API: `POST /api/enrich/trigger` → fires n8n webhook (`/webhook/enrich-pipeline-v2`)
   - State: Pipeline running, progress tracking begins

3. **L1 Company Research** — Perplexity researches each company (industry, size, location, market position)
   - Orchestrated by n8n (workflow `N00qr21DCnGoh32D`)
   - State: Companies get tier assignment (Platinum/Gold/Silver), basic enrichment fields populated

4. **Triage Gate** — Companies filtered by ICP match
   - State: Companies marked Triage: Passed or Triage: Review

5. **L2 Deep Company Research** — Deep dive on passed companies (funding, hiring, recent news, tech stack, leadership)
   - State: L2 enrichment fields populated, company status → Enriched L2

6. **Person Enrichment** — Individual person research (LinkedIn profile, role fit, recent activity)
   - State: Person enrichment fields populated

7. **Monitor progress** — Dashboard shows per-stage completion
   - Screen: `/{namespace}/enrich`
   - API: `GET /api/pipeline/progress` (polls every 10s)
   - State: Progress bars update in real-time

**Cross-Flow Connections**:
- **Feeds into**: FLOW-4 (enriched data enables meaningful filtering), FLOW-5 (enrichment data personalizes messages)
- **Receives from**: FLOW-2 (newly imported contacts need enrichment)

**Gaps**:
- Enrichment still runs through n8n/Airtable, not fully PostgreSQL-native yet
- No automatic re-enrichment when data goes stale
- Cost per enrichment not yet tracked in credit system

---

## FLOW-4: Find ICP-Fit Contacts From a Large List

**Job Statement**: When I have hundreds or thousands of contacts, I want to filter by ICP criteria (industry, company size, seniority, geo, etc.) with real-time counts, so I can build a targeted shortlist for outreach without scrolling through everyone.

**Persona**: Founder / SDR
**Entry Point**: `/{namespace}/contacts` (Radar → Contacts)
**Value Moment**: Filtered shortlist of high-fit prospects matching strategy criteria, ready to assign to a campaign
**Status**: Built

**Steps**:
1. **Open contacts list** — Virtual-scrolled table loads
   - Screen: `/{namespace}/contacts`
   - API: `GET /api/contacts` (paginated, filterable)
   - State: Full contact list displayed

2. **Apply ICP faceted filters** — Select industry, company_size, seniority_level, geo_region, revenue_range, department, job_titles, linkedin_activity
   - Screen: `/{namespace}/contacts` (filter sidebar)
   - API: `POST /api/contacts/filter-counts` (returns counts per facet value)
   - State: Real-time faceted counts update as filters change

3. **Toggle include/exclude** — Each facet supports include (must match) and exclude (must not match)
   - API: Same filter-counts endpoint with include/exclude params
   - State: Filter criteria refined

4. **Search job titles** — Typeahead search for specific titles
   - API: `GET /api/contacts/job-titles?q={query}`
   - State: Title matches added to filter

5. **Review filtered results** — Browse matching contacts with enrichment context
   - Screen: `/{namespace}/contacts` (filtered table)
   - State: Shortlist visible

6. **Drill into contact detail** — Click contact for full profile
   - Screen: `/{namespace}/contacts/{contactId}`
   - API: `GET /api/contacts/{id}`
   - State: Full enrichment data, company data, linked campaigns visible

**Cross-Flow Connections**:
- **Feeds into**: FLOW-5 (filtered contacts assigned to campaigns for message generation)
- **Receives from**: FLOW-1 (ICP criteria from strategy define filter presets), FLOW-2 (imported contacts), FLOW-3 (enriched contacts with filterable data)

**Gaps**:
- No saved filter presets (user re-applies filters each time)
- No "ICP score" computed from strategy — filtering is manual against strategy criteria
- No bulk select → assign to campaign directly from contacts page (must go via campaign page)

---

## FLOW-5: Generate Personalized Outreach at Scale

**Job Statement**: When I have a target list of contacts and a campaign template, I want the AI to generate personalized messages for each contact using their enrichment data and my strategy's messaging angles, so I can review 50+ messages in minutes instead of writing each one manually.

**Persona**: Founder / SDR
**Entry Point**: `/{namespace}/campaigns/{campaignId}` (Reach → Campaign Detail)
**Value Moment**: N personalized messages generated with cost estimate, ready for review
**Status**: Built

**Steps**:
1. **Create or select campaign** — Set name, description, template
   - Screen: `/{namespace}/campaigns`
   - API: `POST /api/campaigns` (create) or `GET /api/campaigns/{id}` (existing)
   - State: Campaign created/loaded

2. **Assign contacts** — Select contacts individually or by company
   - Screen: `/{namespace}/campaigns/{campaignId}` (assignment modal)
   - API: `PATCH /api/campaigns/{id}` (update contact roster)
   - State: Contacts linked to campaign, duplicate detection warns about conflicts

3. **Cost estimation** — System estimates credits before generation
   - API: `GET /api/messages/{id}/regenerate/estimate` (per message) or campaign-level estimate
   - State: Cost displayed to user for approval

4. **Trigger generation** — User approves cost, starts generation
   - API: Message generation endpoint (background job)
   - State: Messages being generated per contact x per channel/step

5. **Generation complete** — Messages appear in campaign
   - API: `GET /api/messages?campaign_id={id}`
   - State: Draft messages stored, ready for review

**Cross-Flow Connections**:
- **Feeds into**: FLOW-6 (generated messages need review before sending)
- **Receives from**: FLOW-4 (filtered contacts), FLOW-1 (messaging angles from strategy), FLOW-3 (enrichment data for personalization)

**Gaps**:
- No A/B variant generation (generate 2 versions per contact for comparison)
- Campaign-level cost estimate (aggregate) not yet implemented — only per-message
- No "generate for new contacts added after initial batch"

---

## FLOW-6: Review and Refine AI-Generated Messages

**Job Statement**: When the AI has generated outreach messages, I want to review each one with contact context visible, approve good ones, edit mediocre ones with reason tags, and regenerate bad ones, so I maintain quality control while the AI learns my preferences.

**Persona**: Founder / SDR
**Entry Point**: `/{namespace}/campaigns/{campaignId}/review` (Reach → Campaign → Review)
**Value Moment**: All messages reviewed — approved, edited with reasoning, or regenerated — creating a feedback signal that improves future generation
**Status**: Built

**Steps**:
1. **Open review page** — Campaign messages loaded with template layout (e.g., LinkedIn + Email 3-step)
   - Screen: `/{namespace}/campaigns/{campaignId}/review`
   - API: `GET /api/messages?campaign_id={id}`
   - State: Messages displayed per contact

2. **Review per contact** — See contact context (enrichment, company) alongside drafted message
   - Screen: Review page with contact card + message preview
   - State: User evaluating message quality

3. **Approve** — Message is good as-is
   - API: `PATCH /api/messages/{id}` (status → approved)
   - State: Message marked approved

4. **Edit + tag reason** — Inline edit with reason selection (tone, personalization, accuracy, brevity, relevance)
   - API: `PATCH /api/messages/{id}` (content + edit_reason)
   - State: Message updated, edit reason captured for learning

5. **Regenerate** — Request new version with different angle
   - API: `POST /api/messages/{id}/regenerate`
   - State: New message generated, old version archived

6. **Batch actions** — Approve all, skip all, regenerate all
   - API: `PATCH /api/messages/batch`
   - State: Bulk status updates

**Cross-Flow Connections**:
- **Feeds into**: FLOW-7 (approved messages ready for export/sending)
- **Receives from**: FLOW-5 (generated messages)
- **Feeds back to**: FLOW-5 (edit reason tags train future generation quality)

**Gaps**:
- Edit reason analytics not yet surfaced ("you edit for tone 40% of the time")
- No side-by-side A/B comparison view
- No "regenerate with specific instruction" (e.g., "make it shorter and more casual")

---

## FLOW-7: Launch Multi-Channel Campaign

**Job Statement**: When all messages are reviewed and approved, I want to export them to my sending channels (Lemlist for email sequences, Resend for transactional, LinkedIn via browser extension), so I can launch the campaign and start reaching prospects.

**Persona**: Founder / SDR
**Entry Point**: `/{namespace}/campaigns/{campaignId}` (Reach → Campaign Detail, post-review)
**Value Moment**: Messages delivered to prospects across channels
**Status**: Partial

**Steps**:
1. **Verify all messages approved** — Campaign status check
   - Screen: `/{namespace}/campaigns/{campaignId}`
   - API: `GET /api/campaigns/{id}` (check message status counts)
   - State: Campaign ready for export (all messages approved)

2. **Select export channel** — Choose Lemlist, Resend, or LinkedIn extension
   - Screen: Campaign detail (export options)
   - State: Channel selected

3. **Export to Lemlist** — Push contacts + messages to Lemlist campaign
   - API: External Lemlist API integration
   - State: Lemlist campaign populated, sequences scheduled

4. **Export to Resend** — Send transactional emails via Resend API
   - API: Resend API integration (BL-090: API key encrypted)
   - State: Emails queued for delivery

5. **LinkedIn via extension** — Browser extension sends LinkedIn messages/connection requests
   - API: `POST /api/extension/activity` (logs send events)
   - State: LinkedIn messages sent, activity logged

**Cross-Flow Connections**:
- **Feeds into**: FLOW-8 (delivery events and responses feed analytics)
- **Receives from**: FLOW-6 (approved messages)

**Gaps**:
- Resend integration partially built (BL-090 encrypts API key, BL-091-093 for webhooks/domain/sender)
- No unified send dashboard showing all channels in one view
- Lemlist integration is manual export, not real-time sync
- LinkedIn extension send is spec'd but not fully deployed
- No scheduling (send at optimal time per timezone)

---

## FLOW-8: Evaluate Results and Improve Next Cycle

**Job Statement**: When my campaign has been running, I want to see which messages got replies, which segments converted, and what patterns the AI spots, so I can improve my strategy and run a better campaign next time.

**Persona**: Founder
**Entry Point**: `/{namespace}/echo` (Echo pillar)
**Value Moment**: Actionable insights that feed back into strategy refinement — closing the Try-Run-Evaluate-Improve loop
**Status**: Planned

**Steps**:
1. **View campaign funnel** — Sent → Opened → Replied → Meeting booked
   - Screen: `/{namespace}/echo`
   - State: Funnel metrics displayed per campaign

2. **Segment analysis** — Performance by industry, company size, persona, messaging angle
   - State: Patterns visible (e.g., "healthcare targets reply 2x to efficiency framing")

3. **AI coaching** — System surfaces recommendations
   - State: Proactive suggestions ("Tuesday sends have 35% higher opens", "ICP says fintech but healthcare converts better")

4. **Feed back to strategy** — User accepts suggestions, strategy document updated
   - Connects to: FLOW-1 (strategy refinement)
   - State: Strategy evolves based on real performance data

**Cross-Flow Connections**:
- **Feeds into**: FLOW-1 (strategy adjustments), FLOW-5 (improved generation based on what works)
- **Receives from**: FLOW-7 (delivery events, replies, engagement data)

**Gaps**:
- Entire flow is planned, not built
- Browser extension activity capture exists but no analytics layer
- No email reply parsing
- No conversion attribution model
- Echo page is placeholder

---

## FLOW-9: Manage Workspace and Team

**Job Statement**: When I'm growing my team, I want to invite users, assign roles (viewer/editor/admin), and manage API tokens, so my team can collaborate with appropriate access controls.

**Persona**: Workspace Admin / Founder
**Entry Point**: `/{namespace}/admin` (Settings gear → Users & Roles)
**Value Moment**: Team members have access with correct permissions, workspace is properly governed
**Status**: Built

**Steps**:
1. **View user list** — See all namespace users with roles
   - Screen: `/{namespace}/admin`
   - API: `GET /api/users`
   - State: User list loaded

2. **Invite new user** — Create user with email and role
   - API: `POST /api/users`
   - State: User created with role assignment

3. **Edit roles** — Change user role (viewer → editor → admin)
   - API: `PATCH /api/users/{id}`
   - State: Permissions updated

4. **Manage API tokens** — Generate/revoke namespace API tokens
   - Screen: `/{namespace}/admin/tokens`
   - API: `POST /api/tokens`, `DELETE /api/tokens/{id}`
   - State: Tokens created/revoked

**Cross-Flow Connections**:
- **Feeds into**: All flows (users need access to use any feature)
- **Receives from**: None (administrative entry point)

**Gaps**:
- No email invitation (user must be told credentials)
- No SSO/OAuth for team login
- No activity audit log per user
- No per-user role-based feature gating (all editors see everything)

---

## FLOW-10: Control LLM Spending

**Job Statement**: When I'm using AI features (enrichment, message generation, research), I want to see what each operation costs in credits, get warnings before I exceed my budget, and understand spending patterns, so I can manage costs without surprise bills.

**Persona**: Workspace Admin / Founder
**Entry Point**: `/{namespace}/llm-costs` (Settings gear → LLM Costs, super_admin only)
**Value Moment**: Full visibility into LLM spending by operation, model, and time period with budget controls
**Status**: Partial

**Steps**:
1. **View cost summary** — Total cost, usage count, avg per operation
   - Screen: `/{namespace}/llm-costs`
   - API: `GET /api/llm-usage/summary`
   - State: Aggregate metrics displayed

2. **Breakdown by operation** — See cost per enrichment, generation, research
   - API: `GET /api/llm-usage/details`
   - State: Per-operation breakdown visible

3. **Breakdown by model** — Claude Haiku vs Opus vs Perplexity costs
   - State: Model-level spending visible

4. **Daily trend** — Bar chart of daily spending
   - State: Spending trend visible

5. **Cost estimate before action** — Before generation/enrichment, see credit cost
   - API: Cost estimation endpoints (per-message, per-batch)
   - State: User informed before spending

**Cross-Flow Connections**:
- **Gates**: FLOW-3 (enrichment cost), FLOW-5 (generation cost)
- **Receives from**: All AI-powered flows log usage

**Gaps**:
- Currently super_admin only — namespace admins see no cost data
- Token/credit system (BL-056) spec'd but not deployed
- No budget limits/alerts (50%/75%/100% warnings)
- No per-user cost attribution
- Shows raw USD, not credits (credit system not yet live)

---

## Cross-Flow Summary

### The Core Loop
Strategy (1) → Import (2) → Enrich (3) → Filter (4) → Generate (5) → Review (6) → Launch (7) → Evaluate (8) → back to Strategy (1)

### Entry Points by Persona
| Persona | Primary Entry | Secondary Entry |
|---------|--------------|-----------------|
| Founder (no strategy) | FLOW-1: Build strategy | FLOW-2: Import contacts |
| Founder (has contacts) | FLOW-2: Import | FLOW-4: Filter contacts |
| SDR (contacts ready) | FLOW-4: Filter | FLOW-5: Generate messages |
| Sales Ops | FLOW-2: Import | FLOW-3: Enrich |
| Workspace Admin | FLOW-9: Manage team | FLOW-10: Control costs |

### Value Moments by Time Investment
| Time | Flow | Value |
|------|------|-------|
| 2 min | FLOW-1 | Complete GTM strategy document |
| 5 min | FLOW-2 | Clean, deduplicated contact list |
| 15 min (async) | FLOW-3 | Full market intelligence on all contacts |
| 1 min | FLOW-4 | Shortlist of ICP-fit prospects |
| 5 min | FLOW-5+6 | 50 personalized messages reviewed |
| 1 min | FLOW-7 | Campaign live across channels |

### Status Overview
| Status | Flows |
|--------|-------|
| Built | 1, 2, 3, 4, 5, 6, 9 |
| Partial | 7, 10 |
| Planned | 8 |
