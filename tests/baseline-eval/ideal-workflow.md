# Ideal End-to-End GTM Workflow

Test Subject: **unitedarts.cz** -- Czech entertainment/circus performance company selling to event agencies.
Test Data: 10 contacts from an xlsx of Czech event managers.

---

## Vision Alignment

The product vision defines a **closed-loop GTM engine**: Try -> Run -> Evaluate -> Improve. The AI is positioned as a "strategist-in-residence" that proactively researches, recommends, and learns. The founder is the CEO who approves and steers -- never the operator.

**North star metrics for the ideal workflow:**
- Founder makes ~1 decision per gate (approve/reject/steer)
- AI does the homework, comes back with findings (not questions)
- Every interaction gathers a decision or delivers a result
- Zero busywork: auto-save, auto-extract, guided flow

---

## Step 1: GTM Strategy Creation

**Phase**: Try (Playbook Phase 1 -- Strategy)
**Vision role**: AI as GTM Consultant

### Description
The user opens the Playbook page and describes their business. The AI proactively creates a comprehensive GTM strategy covering ICP, value propositions, buyer personas, competitive positioning, channel strategy, messaging framework, and qualification criteria. The strategy is auto-saved and auto-extracted as the user and AI collaborate.

### User actions
1. Navigate to Playbook page (`/:namespace/playbook`)
2. In the chat sidebar, describe the business: "I run unitedarts.cz -- we provide circus and entertainment performances for corporate events, team buildings, and galas. Our target customers are event agencies in the Czech Republic."
3. Review the AI-generated strategy document
4. Approve or request edits ("Approve" or "Change the ICP to focus on mid-size agencies with 10-50 employees")

### System actions
- Display Playbook split-view (editor left 60%, chat right 40%)
- Auto-save strategy document with 2.5s debounce
- Auto-extract ICP data after each save (structured extracted_data)
- Version each AI edit for undo support

### AI/Chat actions
- Proactively research unitedarts.cz website (using web_search tool)
- Generate a complete strategy document with all sections filled:
  - Executive Summary (unitedarts.cz business context)
  - ICP (event agencies, corporate clients, specific criteria)
  - Buyer Personas (event manager, marketing director, CEO of agency)
  - Value Proposition (unique entertainment, professional production, Czech market expertise)
  - Competitive Positioning (vs other entertainment providers)
  - Channel Strategy (email, LinkedIn, event industry networks)
  - Messaging Framework (tone, angles, pain points)
  - Metrics & KPIs (target response rates, meetings)
  - 90-Day Action Plan
- Write the strategy directly into the editor (using strategy tools)
- Explain what it did: "I've researched unitedarts.cz and built your GTM strategy. Here's what I found..."
- Ask for approval: "Does this capture your business correctly? Shall I proceed to contact selection?"

### Expected outputs
- Complete strategy document in the editor (all 9 sections)
- Structured extracted_data (ICP criteria, value props, qualification rules)
- Chat history with research findings and recommendations
- Strategy version history for undo

### User-input gate
- **Approve strategy** (confirm the document is accurate and complete enough to proceed)
- Minimum: 1 user message (business description) + 1 approval

### Ideal user interactions
- 2 total: 1 business description + 1 approval
- Stretch: 1 if AI can detect the namespace/company context automatically

### LLM nodes involved
- `web_search` (Perplexity sonar -- research company website)
- `strategy_write` (Claude -- generate strategy sections)
- `strategy_extract` (Claude -- extract ICP data from document)
- Chat response generation (Claude Opus/Sonnet -- conversational)

---

## Step 2: Intelligence Extraction

**Phase**: Try (Playbook Phase 1 -> transition to Phase 2)
**Vision role**: AI as Analyst

### Description
The system extracts structured data from the approved strategy: scoring rubric, qualification filters, message templates, ICP criteria. This data drives downstream automation (contact filtering, triage rules, message generation). The AI explains what it extracted and asks for confirmation.

### User actions
1. Review the extracted criteria summary presented by the AI
2. Confirm or adjust: "Yes, that's correct" or "Add 'conference organizer' to the job titles"

### System actions
- Auto-extract ICP data from strategy document (triggered by save/approve)
- Store structured extracted_data in StrategyDocument model
- Map ICP criteria to contact filter parameters (industry, geography, company size, seniority)

### AI/Chat actions
- Present extraction summary: "I've extracted your qualification criteria and messaging angles. Here's what I'll use to filter contacts..."
  - Industries: event management, marketing agencies, conference organizers
  - Geography: Czech Republic (primarily), Slovakia
  - Company size: 10-50 employees
  - Job titles: event manager, marketing director, project manager
  - Qualification signals: active event portfolio, corporate client list
- Ask for confirmation before proceeding to contacts phase
- Suggest proceeding: "Ready to find matching contacts? I'll switch to the Contacts phase."

### Expected outputs
- Structured ICP data stored in extracted_data
- Filter parameters ready for contact matching
- Qualification rules defined (triage criteria)

### User-input gate
- **Confirm extraction** (validate that the extracted criteria match intent)
- Minimum: 1 confirmation message

### Ideal user interactions
- 1 total: confirmation

### LLM nodes involved
- `strategy_extract` (Claude -- extract structured data from markdown)
- Chat response (Claude -- present summary)

---

## Step 3: Contact Import

**Phase**: Run (Playbook Phase 2 -- Contacts, or separate Import page)
**Vision role**: AI as Sourcing Assistant

### Description
The user uploads an xlsx/csv file containing 10 Czech event manager contacts. The system parses the file, maps columns automatically, shows a preview, and imports the contacts. The AI guides the user through the process and flags any data quality issues.

### User actions
1. Navigate to Import page (`/:namespace/import`) or use the Playbook contacts phase
2. Upload the xlsx file (drag-and-drop or file picker)
3. Review column mapping (should be auto-detected)
4. Review preview (10 contacts, dedup status)
5. Click "Import" to execute

### System actions
- Parse xlsx/csv file and detect columns
- Auto-map columns to system fields (first_name, last_name, email, company, job_title)
- Run dedup check against existing contacts
- Show preview with 10 rows and mapping results
- Execute import (create contacts + companies)
- Assign to a tag/batch for tracking

### AI/Chat actions
- Guide the import: "I see your file has 10 contacts. The columns map to: first_name, last_name, email, company, job_title."
- Flag data quality issues: "2 contacts are missing email addresses. 1 company name looks like an abbreviation."
- Confirm successful import: "10 contacts imported successfully. 8 new companies created."
- Suggest next step: "Shall I run enrichment to fill in missing company data?"

### Expected outputs
- 10 contacts in the database with company associations
- ~8-10 companies created (depending on overlap)
- Import job record with results
- Tag assignment for the batch

### User-input gate
- **Confirm import** (after reviewing preview)
- Minimum: 1 file upload + 1 confirm click

### Ideal user interactions
- 2 total: upload file + confirm import
- The column mapping and preview should require zero corrections if auto-detection works

### LLM nodes involved
- `csv_mapper` (Claude -- AI-assisted column mapping)
- Chat response (optional -- guidance messages)

---

## Step 4: Basic Enrichment (L1)

**Phase**: Run (Enrich page or Playbook-triggered)
**Vision role**: AI as Research Analyst

### Description
Run L1 enrichment on the imported companies to gather basic company profiles. L1 uses Perplexity sonar to scrape company websites and generate structured profiles (industry, size, revenue, B2B/B2C, key offerings). Results feed into triage/qualification.

### User actions
1. Navigate to Enrich page (`/:namespace/enrich`) or accept AI suggestion from chat
2. Select L1 stage (should be pre-selected or auto-suggested)
3. Review cost estimate
4. Click "Run" to start enrichment

### System actions
- Calculate cost estimate (10 companies x $0.02 = ~$0.20)
- Execute L1 enrichment via DAG executor
- For each company: query Perplexity sonar, parse response, store in company_enrichment_l1
- QC check results (name mismatch, data completeness)
- Update entity_stage_completions records
- Show real-time progress (10/10 completed)

### AI/Chat actions
- Suggest enrichment proactively: "Your 10 contacts need company data. Shall I run L1 enrichment? Estimated cost: 200 credits."
- Report progress: "L1 enrichment complete. 9/10 companies enriched successfully. 1 company (XYZ) had no website found."
- Summarize findings: "Key insights: 7 companies are event agencies (matching your ICP), 2 are corporate clients, 1 is unrelated."
- Suggest next step: "Ready to run triage? This will qualify companies against your ICP criteria."

### Expected outputs
- L1 enrichment data for 10 companies
- Company profiles (industry, size, revenue estimate, B2B flag, offerings)
- QC flags for any data quality issues
- Entity stage completion records (l1 = complete)

### User-input gate
- **Approve enrichment run** (after cost estimate)
- Minimum: 1 approval

### Ideal user interactions
- 1 total: approve the run (or 0 if AI auto-runs from playbook context)

### LLM nodes involved
- L1 enricher (Perplexity sonar -- 10 company queries)
- QC checker (rules-based, no LLM)
- Chat response (Claude -- summarize results)

---

## Step 5: Qualification & Triage

**Phase**: Run (automatic post-L1)
**Vision role**: AI as Qualification Engine

### Description
Run triage evaluation on enriched companies using the ICP criteria extracted from the strategy. Companies are classified as Passed, Review, or Disqualified based on configurable rules (tier, industry, geography, revenue, B2B flag). The user reviews borderline cases.

### User actions
1. Review triage results (should be auto-triggered after L1)
2. Approve or override borderline cases in the QC review queue
3. Confirm qualified set

### System actions
- Execute triage stage using rules from strategy extracted_data
- Apply filters: industry allowlist (event management, marketing), geo (CZ/SK), B2B required
- Classify: Passed (matches ICP), Review (partial match), Disqualified (no match)
- Update company status (Triage: Passed / Triage: Review / Disqualified)
- Present results in enrichment review queue

### AI/Chat actions
- Report triage results: "Triage complete. 7 companies passed (event agencies matching your ICP). 2 need your review. 1 disqualified (retail, not B2B)."
- For review cases: "Company ABC matches on geography and size but is a PR agency, not an event agency. Keep or disqualify?"
- Suggest proceeding: "7 qualified companies with 8 contacts ready for deep enrichment."

### Expected outputs
- Company status updated (Passed/Review/Disqualified)
- Triage reasons stored per company
- Qualified contact list (contacts whose companies passed triage)

### User-input gate
- **Review borderline cases** (0-3 decisions depending on data quality)
- **Confirm qualified set** to proceed

### Ideal user interactions
- 1-3 total: 0-2 review decisions + 1 confirmation

### LLM nodes involved
- Triage evaluator (rules-based, no LLM, $0 cost)
- Chat response (Claude -- summarize and present review cases)

---

## Step 6: Deep Enrichment (L2 + Person + Registry)

**Phase**: Run (Enrich page)
**Vision role**: AI as Research Analyst (Deep)

### Description
Run L2 deep research on qualified companies and person-level enrichment on their contacts. For Czech companies, also run ARES registry enrichment. This provides the detailed intelligence needed for personalized message generation.

### User actions
1. Review cost estimate for L2 + Person + Registry stages
2. Approve the run
3. Wait for completion (monitor progress bar)

### System actions
- Calculate cost estimate (7 companies x L2 $0.08 + 8 contacts x Person varies + Registry $0.00)
- Execute DAG with stages: L2, Person, Registry (ARES for CZ companies)
- L2: Deep company analysis (strategic signals, market position, pain points, opportunities)
- Person: Contact-level enrichment (role context, social presence, talking points)
- Registry: ARES data for Czech companies (legal form, capital, directors, NACE codes)
- Track progress per entity per stage

### AI/Chat actions
- Suggest the run: "Deep enrichment will give us the intel needed for personalized messages. Cost estimate: ~800 credits."
- Report progress: "L2 research complete for 7 companies. Person enrichment running... 6/8 done."
- Highlight key findings: "ARES confirms 5 companies are s.r.o. (Czech LLC). 2 companies have interesting strategic signals: ABC is expanding into corporate events, DEF just hired a new business development director."
- Suggest next step: "Enrichment complete. Ready to create a campaign and generate messages?"

### Expected outputs
- L2 enrichment (company_enrichment_profile, signals, market, opportunity)
- Person enrichment (contact_enrichment with scoring, career, social data)
- Registry data (company_legal_profile for CZ companies via ARES)
- Entity stage completions for all stages

### User-input gate
- **Approve enrichment run** (after cost estimate)
- Minimum: 1 approval

### Ideal user interactions
- 1 total: approve the run

### LLM nodes involved
- L2 enricher (Perplexity/Claude -- 7 company deep research queries)
- Person enricher (Perplexity/Claude -- 8 contact queries)
- Registry (ARES API -- no LLM, free)
- Chat response (Claude -- summarize findings)

---

## Step 7: Campaign Creation

**Phase**: Run (Playbook Phase 4 or Campaigns page)
**Vision role**: AI as Campaign Architect

### Description
Create a campaign for the outreach. The system automatically selects qualified contacts, configures outreach steps (LinkedIn connect + email follow-up), and sets up the campaign structure. The AI uses the strategy's channel recommendations and messaging framework.

### User actions
1. Accept AI suggestion to create campaign (or navigate to Campaigns page)
2. Review campaign configuration (name, contacts, template steps)
3. Confirm creation

### System actions
- Create campaign with strategy-derived settings
- Add qualified contacts to campaign (7-8 contacts that passed triage + enrichment)
- Apply campaign template (e.g., LinkedIn + Email 2-step)
- Run enrichment readiness check (verify all contacts have sufficient data)
- Configure sender settings (from_email, from_name)
- Run conflict check (no contacts in overlapping active campaigns)

### AI/Chat actions
- Propose campaign: "I'll create a campaign called 'Czech Event Agencies - Q1 2026' with your 8 qualified contacts."
- Select template: "Based on your channel strategy, I recommend LinkedIn Connect first, then email follow-up. Here's the template..."
- Verify readiness: "All 8 contacts have sufficient enrichment data for personalized messaging."
- Ask for approval: "Ready to generate messages?"

### Expected outputs
- Campaign record created
- 8 contacts assigned to campaign
- Template steps configured (linkedin_connect + email)
- Enrichment readiness verified
- No conflicts detected

### User-input gate
- **Approve campaign creation** (confirm contacts, template, and settings)
- Minimum: 1 approval

### Ideal user interactions
- 1 total: approve the campaign setup

### LLM nodes involved
- Chat response (Claude -- propose and configure)
- No LLM for campaign creation itself (CRUD operations)

---

## Step 8: Message Generation

**Phase**: Run (Campaign detail -> Generation tab)
**Vision role**: AI as Messaging Coach

### Description
Generate personalized outreach messages for each contact in the campaign. Messages use the strategy's messaging framework, company enrichment data, and person-level intelligence. Each message is tailored to the specific contact's role, company context, and potential pain points.

### User actions
1. Review cost estimate for message generation
2. Approve generation
3. Wait for completion

### System actions
- Calculate cost estimate (8 contacts x 2 steps x token estimate)
- Execute background generation (Claude Haiku per message)
- For each contact + step: build prompt with company summary, L2 intel, person enrichment, strategy messaging framework
- Generate subject line (email) + body
- Apply channel constraints (LinkedIn connect <= 300 chars, email with subject)
- Track progress (16 messages total: 8 LinkedIn + 8 email)
- Log costs per message via LlmUsageLog

### AI/Chat actions
- Explain what it's doing: "Generating personalized messages for 8 contacts across 2 channels. Each message uses their company research and your messaging framework."
- Report completion: "16 messages generated. Average cost: 50 credits per message."
- Highlight variety: "Messages reference specific company details -- ABC's corporate event expansion, DEF's new BD director hire."
- Suggest review: "Messages are ready for your review. Shall I open the review queue?"

### Expected outputs
- 16 messages (8 LinkedIn connect + 8 email follow-up)
- Each message personalized with enrichment data
- Cost logged per message
- Generation status: complete

### User-input gate
- **Approve generation** (after cost estimate)
- Minimum: 1 approval

### Ideal user interactions
- 1 total: approve generation

### LLM nodes involved
- Message generator (Claude Haiku -- 16 generation calls)
- Prompt builder (uses strategy messaging framework + enrichment data)
- Chat response (Claude -- progress updates)

---

## Step 9: Message Review & Approval

**Phase**: Run (Campaign detail -> Review tab)
**Vision role**: AI as Quality Reviewer

### Description
Review each generated message in the focused review queue. The user approves, edits, or rejects each message. The AI provides context for each message (why it chose specific talking points) and allows regeneration with feedback.

### User actions
1. Open review queue
2. For each message: approve, edit, reject, or regenerate
3. For edits: modify text inline
4. For regeneration: provide feedback ("make it shorter", "emphasize the entertainment aspect more")
5. Complete review (all messages reviewed)

### System actions
- Present messages in sequential review queue (one at a time)
- Show contact context alongside message (company, enrichment highlights)
- Track review status (approved/rejected/pending)
- Save edits with version tracking (original preserved)
- Execute regeneration on demand (with cost estimate)
- Calculate review summary stats

### AI/Chat actions
- Provide context: "This message to Jan Novak at EventPro references their recent corporate event expansion -- I found this in their L2 research."
- Suggest improvements: "The LinkedIn connect message is 285/300 characters. If you want to add a personal touch, I can try a shorter version."
- Accept feedback for regeneration: "Regenerating with more emphasis on entertainment quality. Estimated cost: 50 credits."

### Expected outputs
- All 16 messages reviewed (approved/rejected/edited)
- Edit history preserved (original_body, original_subject, edit_reason)
- Regenerated messages (if any) with cost logged
- Review summary: X approved, Y rejected, Z edited

### User-input gate
- **Review each message** (approve/reject/edit per message)
- This is the highest-effort step -- by design (humans should approve outreach)

### Ideal user interactions
- 8-16 total (1 per message for approve, 2 per message if editing)
- Target: 80%+ approved without edits (good generation quality)

### LLM nodes involved
- Regeneration (Claude Haiku -- only for rejected/regenerated messages)
- Chat response (Claude -- context and suggestions)

---

## Step 10: Campaign Launch (Outreach)

**Phase**: Run (Campaign detail -> Outreach tab)
**Vision role**: AI as Campaign Manager

### Description
Send approved messages through configured channels. Email goes via Resend API, LinkedIn messages are queued for Chrome extension pickup. The system provides a final approval gate before sending.

### User actions
1. Open Outreach tab
2. Review outreach approval dialog (summary: X emails, Y LinkedIn messages)
3. Approve send
4. Monitor send status

### System actions
- Show outreach approval dialog with counts and channel breakdown
- Verify all messages are reviewed (approval gate)
- Send emails via Resend API (rate limited, idempotent)
- Queue LinkedIn messages for Chrome extension
- Track per-message send status
- Update campaign status to exported/sent

### AI/Chat actions
- Present send summary: "Ready to send: 8 emails and 8 LinkedIn connects. All messages approved."
- Confirm channels: "Emails will send from your configured sender. LinkedIn messages will queue for your extension."
- Report status: "8 emails sent successfully. 8 LinkedIn messages queued -- open your extension to execute."

### Expected outputs
- Emails sent via Resend (with tracking)
- LinkedIn messages queued in LinkedInSendQueue
- Send status per message (sent/queued/failed)
- Campaign status updated

### User-input gate
- **Final send approval** (confirm outreach launch)
- Minimum: 1 approval

### Ideal user interactions
- 1 total: approve the send

### LLM nodes involved
- None (sending is API-based, no LLM)
- Chat response (Claude -- status updates)

---

## Workflow Summary

| Step | Name | Phase | Min User Actions | Primary Gate |
|------|------|-------|-----------------|--------------|
| 1 | GTM Strategy Creation | Try | 2 (describe + approve) | Approve strategy |
| 2 | Intelligence Extraction | Try | 1 (confirm) | Confirm extraction |
| 3 | Contact Import | Run | 2 (upload + confirm) | Confirm import |
| 4 | Basic Enrichment (L1) | Run | 1 (approve run) | Approve cost |
| 5 | Qualification & Triage | Run | 1-3 (review + confirm) | Confirm qualified set |
| 6 | Deep Enrichment (L2+) | Run | 1 (approve run) | Approve cost |
| 7 | Campaign Creation | Run | 1 (approve) | Approve campaign |
| 8 | Message Generation | Run | 1 (approve) | Approve cost |
| 9 | Message Review | Run | 8-16 (per message) | Approve each message |
| 10 | Campaign Launch | Run | 1 (approve) | Final send approval |

**Total minimum user interactions**: ~20-30 (dominated by message review, which is intentionally human-in-the-loop)

**Total without message review**: ~12 interactions for the entire GTM workflow from zero to outreach launch.

---

## Gap Analysis: Current System vs. Ideal

### Fully Available (should work as described)
- Strategy creation with AI chat (Playbook Phase 1)
- ICP extraction from strategy
- CSV/XLSX import with column mapping
- L1 enrichment (Perplexity sonar)
- Triage evaluation (rules-based)
- L2/Person enrichment
- Registry enrichment (ARES for CZ)
- Campaign creation and contact assignment
- Message generation (Claude Haiku)
- Message review queue
- Email sending (Resend)
- LinkedIn queuing

### Potentially Incomplete (needs testing)
- AI proactiveness (does the chat suggest next steps automatically?)
- Seamless phase transitions (does the system auto-advance or require manual navigation?)
- Strategy-to-filter pipeline (how smooth is the ICP extraction -> contact filter flow?)
- Chat context continuity across phases (does the AI remember the strategy context when generating messages?)
- Error recovery (what happens when enrichment fails for some entities?)

### Known Gaps (per vision vs. current)
- Echo Analytics (placeholder only -- no campaign performance tracking)
- Closed-loop learning (no campaign result -> strategy refinement cycle yet)
- Voice dialog (not implemented)
- AI Avatar (not implemented)
- Proactive check-ins / follow-ups (not implemented)
- A/B message variants (not implemented)
- Network intelligence (not implemented)
