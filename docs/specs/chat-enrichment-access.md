# Spec: Chat Access to Self-Company Enrichment Data (BL-054)

**Date**: 2026-02-23 | **Status**: Spec'd
**Priority**: Must Have | **Effort**: M
**Dependencies**: AGENT (agent-ready chat architecture)

---

## Problem Statement

The playbook onboarding flow (`POST /api/playbook/research`) runs L1 + L2 enrichment on the tenant's own company and seeds the strategy document with structured research data. After onboarding, the chat system prompt includes this enrichment data via `_load_enrichment_data()` and `_format_enrichment_for_prompt()`.

However, there are two gaps:

### Gap 1: Missing L2 Fields in Chat Context

`_load_enrichment_data()` in `playbook_routes.py` loads only a subset of available enrichment data. Several valuable fields from the enrichment tables are omitted:

**From `CompanyEnrichmentL2`** (not loaded):
- `relevant_case_study` — relevant case studies for the company
- `eu_grants` — EU grants/funding data
- `ai_hiring` — AI-specific hiring signals
- `tech_partnerships` — technology partnership info
- `industry_pain_points` — industry-wide pain analysis
- `cross_functional_pain` — cross-functional pain points
- `adoption_barriers` — barriers to adoption
- `competitor_ai_moves` — competitor AI strategy moves
- `expansion` — new markets, offices, contracts
- `workflow_ai_evidence` — AI/automation evidence
- `revenue_trend` — growing/stable/declining/restructuring
- `growth_signals` — headcount growth, new offices
- `regulatory_pressure` — applicable regulations
- `employee_sentiment` — review ratings and themes
- `pitch_framing` — recommended pitch approach
- `ma_activity` — recent M&A activity
- `tech_stack_categories` — structured tech stack by category
- `fiscal_year_end` — fiscal year end month
- `digital_maturity_score` — 1-10 digital maturity rating
- `it_spend_indicators` — evidence of IT investment level

**From `CompanyEnrichmentOpportunity`** (not loaded at all):
- `industry_pain_points`
- `cross_functional_pain`
- `adoption_barriers`

**From `CompanyEnrichmentMarket`** (partially loaded):
- `eu_grants` — not loaded
- `media_sentiment` — not loaded
- `press_releases` — not loaded
- `thought_leadership` — not loaded

**From `CompanyEnrichmentSignals`** (partially loaded):
- `leadership_changes` — not loaded
- `ai_hiring` — not loaded
- `tech_partnerships` — not loaded
- `competitor_ai_moves` — not loaded
- `news_confidence` — not loaded
- `job_posting_count` — not loaded
- `hiring_departments` — not loaded

**From `CompanyRegistryData` / `CompanyLegalProfile`** (not loaded at all):
- Legal entity info, directors, credibility score, insolvency data

### Gap 2: Chat Cannot Access Enrichment Without Prior Onboarding

If the tenant's company has been enriched (e.g., it exists as `is_self=True` in the companies table), but the strategy document's `enrichment_id` was never linked (user skipped onboarding), the chat has zero enrichment context. There is no fallback lookup.

### Gap 3: No On-Demand Refresh

If enrichment data becomes stale or was only partially completed (L2 failed), the chat cannot trigger a re-enrichment. The user must go through the onboarding flow again.

---

## What Data Should Be Accessible

### Tier 1: Always Injected into System Prompt (current + additions)

Data injected into every chat turn's system prompt. This is what the AI "knows" about the company without being asked.

**Currently included** (no change):
- Company profile (name, domain, industry, category, size, revenue, HQ, tier, status)
- L1 triage (triage_notes, pre_score, confidence)
- L2 overview (company_intel, ai_opportunities, pain_hypothesis, quick_wins)
- Profile (company_intel, key_products, customer_segments, competitors, tech_stack, leadership_team, certifications)
- Signals (digital_initiatives, hiring_signals, ai_adoption_level, growth_indicators)
- Market (recent_news, funding_history)

**Add to system prompt** (high-value, always relevant for strategy):
- `pitch_framing` (L2) — directly actionable for messaging
- `revenue_trend` (L2) — critical for positioning
- `industry_pain_points` (L2/Opportunity) — core strategy input
- `relevant_case_study` (L2/Opportunity) — proof points for messaging

### Tier 2: Available via Enrichment Tool (on-demand)

Remaining fields are too verbose for the system prompt but should be accessible when the AI needs them. This requires the agent-ready chat architecture (tool-use).

**Tool: `get_company_research(section)`**

Sections:
- `legal` — CompanyLegalProfile: registration, directors, credibility score, insolvency
- `signals_detail` — Full signals: leadership_changes, ai_hiring, tech_partnerships, competitor_ai_moves, job_posting_count, hiring_departments
- `market_detail` — Full market: eu_grants, media_sentiment, press_releases, thought_leadership
- `opportunity_detail` — Full opportunity: cross_functional_pain, adoption_barriers, industry_pain_points
- `strategic` — L2 strategic fields: regulatory_pressure, employee_sentiment, expansion, workflow_ai_evidence, growth_signals, ma_activity
- `tech_detail` — tech_stack_categories, digital_maturity_score, it_spend_indicators, fiscal_year_end

---

## User Stories

1. As a founder using the playbook chat, I want the AI to reference my company's enrichment data (industry pains, competitive landscape, revenue trends) when helping me build strategy, so its advice is grounded in real research rather than generic.

2. As a founder who skipped onboarding, I want the chat to still find and use my company's enrichment data if it exists, so I don't have to re-trigger research just to get context-aware advice.

3. As a founder, I want to ask the chat "what do you know about my company's hiring signals?" and get detailed data from the enrichment tables, so I can drill into specific research areas during strategy sessions.

4. As a founder, I want the AI to tell me when enrichment data is missing or stale, so I know when to trigger a refresh.

---

## Acceptance Criteria

### AC-1: System Prompt Includes Full Tier 1 Data

**Given** a tenant has a self-company with L2 enrichment completed
**When** the user sends any chat message
**Then** the system prompt includes `pitch_framing`, `revenue_trend`, `industry_pain_points`, and `relevant_case_study` in addition to all currently included fields

### AC-2: Fallback Self-Company Lookup

**Given** a tenant's strategy document has no `enrichment_id` set
**And** the tenant has a company with `is_self=True`
**When** the user sends a chat message
**Then** the system automatically loads enrichment data from the self-company
**And** links the document's `enrichment_id` for future requests

### AC-3: Enrichment Status Awareness

**Given** a tenant has no self-company or no enrichment data
**When** the user asks a question that would benefit from company research
**Then** the AI mentions that company research hasn't been done yet
**And** suggests the user trigger research from the onboarding flow (or via a future tool)

### AC-4: On-Demand Enrichment Detail (Future — requires AGENT)

**Given** the chat has tool-use architecture enabled
**And** the user asks about detailed hiring signals or legal data
**When** the AI needs specific enrichment data not in the system prompt
**Then** it calls `get_company_research("signals_detail")` and incorporates the results

---

## Implementation Plan

### Phase 1: Expand System Prompt Context (No Dependencies)

1. **Update `_load_enrichment_data()`** in `api/routes/playbook_routes.py`:
   - Add `pitch_framing`, `revenue_trend`, `relevant_case_study` from L2
   - Add `industry_pain_points` from L2 or CompanyEnrichmentOpportunity

2. **Update `_format_enrichment_for_prompt()`** in `api/services/playbook_service.py`:
   - Add "STRATEGIC POSITIONING" section with `pitch_framing` and `revenue_trend`
   - Add "INDUSTRY CONTEXT" section with `industry_pain_points`
   - Add "PROOF POINTS" section with `relevant_case_study`

3. **Add fallback self-company lookup** in `post_chat_message()`:
   ```python
   if not doc.enrichment_id:
       self_company = Company.query.filter_by(
           tenant_id=tenant_id, is_self=True
       ).first()
       if self_company:
           doc.enrichment_id = self_company.id
           db.session.commit()
           enrichment_data = _load_enrichment_data(self_company.id)
   ```

### Phase 2: Enrichment Detail Tool (Requires AGENT)

4. **Add `get_company_research` tool** to the tool-use registry:
   - Accepts `section` parameter (legal, signals_detail, market_detail, etc.)
   - Queries appropriate enrichment tables
   - Returns formatted text for AI to incorporate

5. **Add enrichment status to system prompt**:
   - Include a line like "Company research status: completed (L1 + L2)" or "partial (L1 only, L2 failed)"
   - If no research exists: "No company research available. Suggest the user trigger research."

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| No self-company exists | AI gives generic advice; mentions research isn't done |
| L1 done, L2 failed | Partial data loaded; AI notes some research is incomplete |
| L2 in progress (background thread) | System prompt uses whatever is available; research status shows "in_progress" |
| Stale data (enriched months ago) | Include `enriched_at` in prompt so AI can note data age |
| Multiple self-companies (shouldn't happen) | Use the first one found; log a warning |
| Strategy doc linked to non-self company | Use whatever company is linked (existing behavior) |

---

## Files Changed

| File | Change |
|------|--------|
| `api/routes/playbook_routes.py` | Expand `_load_enrichment_data()`, add self-company fallback |
| `api/services/playbook_service.py` | Expand `_format_enrichment_for_prompt()` with new sections |
| `api/routes/playbook_routes.py` | (Phase 2) Add tool handler for `get_company_research` |

---

## Out of Scope

- Triggering enrichment from chat (requires full pipeline integration)
- Contact-level enrichment in chat context (separate feature)
- Cross-tenant enrichment data sharing
- Enrichment cost display in chat
