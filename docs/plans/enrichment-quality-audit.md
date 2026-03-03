# Enrichment Quality Audit Report

**Date**: 2026-03-02
**Sprint**: Sprint 6 Planning Input
**Status**: Complete — 12 backlog items created

---

## Executive Summary

A comprehensive three-track evaluation of the leadgen pipeline's enrichment system reveals critical data flow bugs that render large portions of enrichment output invisible to users. The L2 enrichment write/read mismatch (enricher writes to a monolithic table while the API reads from split tables) means ALL companies enriched after migration 021 have no visible L2 data. Person enrichment suffers a 99% pipeline failure rate and discards 12 of 20+ LLM-generated fields even when it succeeds. These P0 bugs nullify significant infrastructure investment — the enrichment prompts produce high-quality output (L2 scores 7.5/10, messages 8.5/10), but the data never reaches users. Fixing the three P0 items alone would unlock approximately 40+ fields of already-generated intelligence across company and contact detail pages. Combined composite score: **6.2/10** — dragged down by data flow bugs masking otherwise strong enrichment quality.

---

## Methodology

Three parallel evaluation tracks were executed simultaneously, each with distinct focus and tooling:

| Track | Focus | Method |
|-------|-------|--------|
| **Architecture Review** | End-to-end data flow from LLM output to frontend render | Code audit of enricher services, API routes, DB migrations, and frontend components. Field-by-field tracing from prompt → enricher → DB → API → UI. |
| **Data Quality Testing** | Actual enrichment output quality on production data | Sampled companies and contacts across batches. Evaluated completeness, accuracy, cost efficiency, and failure rates per pipeline stage. |
| **UI/UX Experience** | Entity detail page usability and information architecture | Evaluated company/contact detail pages across 6 dimensions: IA, visual design, completeness, usability, data quality signals, missing features. |

---

## Findings by Severity

### P0 — CRITICAL (3 items)

#### P0-1: L2 Enrichment Write/Read Mismatch

**Impact**: ALL companies enriched after migration 021 have NO visible L2 data in the frontend.

- **Root cause**: The L2 enricher (`api/services/l2_enricher.py`) writes exclusively to the `company_enrichment_l2` monolithic table. The API (`api/routes/company_routes.py`) reads from four split tables: `company_enrichment_profile`, `company_enrichment_signals`, `company_enrichment_market`, `company_enrichment_opportunity`.
- **Fields affected**: 25+ fields including company_intel, key_products, customer_segments, competitors, tech_stack, leadership_team, certifications, recent_news, funding_history, eu_grants, pain_hypothesis, ai_opportunities, quick_wins, industry_pain_points, cross_functional_pain, adoption_barriers, expansion, workflow_ai_evidence, revenue_trend, growth_signals, regulatory_pressure, employee_sentiment, pitch_framing, ma_activity, digital_maturity_score, it_spend_indicators.
- **Fix**: Update enricher to write to split tables (canonical), OR update API to read from monolithic table. Recommendation: update enricher to write to split tables, since the API and frontend are already built around that schema.

#### P0-2: Person Enrichment Data Loss — 12 Fields Produced But Never Stored

**Impact**: Person enricher generates rich LLM output but discards 12 of 20+ fields. Frontend has UI sections built for all these fields that are permanently empty.

- **Root cause**: `_upsert_contact_enrichment()` in `api/services/person_enricher.py` only maps 9 of 20+ fields returned by the LLM prompt.
- **Fields discarded**: education, certifications, expertise_areas, budget_signals, buying_signals, pain_indicators, technology_interests, personalization_angle, connection_points, conversation_starters, objection_prediction, previous_companies.
- **Fix**: Add missing columns to `contact_enrichment` table via migration, update the upsert method to include all fields.

#### P0-3: Person Enrichment 99% Pipeline Failure Rate

**Impact**: Only 1 out of 100+ contacts has ever been successfully person-enriched. The entire person enrichment stage is effectively non-functional.

- **Root cause**: Requires investigation. Possible causes include: eligibility filter too restrictive, sub-workflow error handling silently swallowing failures, rate limiting, or prompt failures.
- **Fix**: Investigate execution logs, trace a sample of failed contacts through the pipeline, identify and fix root cause.

### P1 — HIGH (4 items)

#### P1-1: Split L2 Tables Missing Fields from Migration 028

Migration 028 added new fields to the monolithic `company_enrichment_l2` table but never propagated them to the split tables.

- **Missing from `company_enrichment_signals`**: regulatory_pressure, employee_sentiment, digital_maturity_score, fiscal_year_end, it_spend_indicators, tech_stack_categories
- **Missing from `company_enrichment_market`**: expansion, workflow_ai_evidence, revenue_trend, growth_signals, ma_activity
- **Missing from `company_enrichment_opportunity`**: pitch_framing

#### P1-2: API Signal Fields Not Returned

The company detail API endpoint for the signals module only SELECTs the original 11 fields. Even after the DB schema is fixed, 6 new signal fields would not appear in API responses.

#### P1-3: Copy-to-Clipboard Missing on All Fields

Sales reps frequently copy enrichment data to CRMs, email drafts, and notes. No copy button exists on any field in entity detail pages. This is a significant daily friction point.

#### P1-4: Data Quality Insights Buried in Text

QC flags, contradictions, and research gaps are embedded within Company Intel text blobs. Users must read entire paragraphs to find critical data quality warnings. A structured "Data Quality" card at the top of the Intelligence tab would surface these immediately.

### P2 — MEDIUM (3 items)

#### P2-1: Enrichment Completeness Gauge

No indicator showing enrichment progress (e.g., "75% enriched — missing: revenue, tech leadership"). Users cannot assess data readiness at a glance.

#### P2-2: Company Logo Not Rendered

The `logo_url` field exists in the data model and is populated for some companies, but is not rendered in the entity detail header. Low effort, high visual impact.

#### P2-3: Data Freshness Indicators

No visual flag for data enriched 90+ days ago. Users have no way to distinguish fresh data from stale data without checking enrichment timestamps manually.

### P3 — LOW (2 items)

#### P3-1: Quality/Confidence Scores Never Populated

`quality_score` and `confidence_score` in `research_directory` are always 0. No feedback loop exists for enrichment quality measurement.

#### P3-2: previous_companies Never Mapped

The `previous_companies` column exists in the DB, the API returns it, but the person enricher never populates it. The LLM prompt produces `career_highlights` which contains this data but is not mapped.

---

## Dimension Scores

| Dimension | Score | Key Finding |
|-----------|-------|-------------|
| **L1 Enrichment** | 6.0/10 | Core fields populated; HQ location gaps; legacy batch much worse |
| **Triage** | 7.5/10 | Structured, cost-effective ($0.006/company), correct routing; revenue never verified |
| **L2 Enrichment** | 7.5/10 | Excellent depth when populated (executive briefs, pain hypotheses); data invisible due to P0-1 |
| **Person Enrichment** | 2.0/10 | 99% failure rate (P0-3); 12-field data loss even on success (P0-2) |
| **Message Generation** | 8.5/10 | Personalized, multi-channel, good quality; relies only on company data (no person data) |
| **Architecture Integrity** | 4.0/10 | Critical write/read mismatch; split/monolithic table ambiguity; multiple data loss paths |
| **Information Architecture** | 7.0/10 | 4-tab layout well-designed; progressive disclosure effective |
| **Visual Design** | 7.0/10 | Clean, consistent; ModuleSummaryCards effective |
| **UI Completeness** | 5.0/10 | 25+ built fields permanently empty due to data flow bugs |
| **Usability** | 7.0/10 | Inline editing good; missing copy-to-clipboard, freshness indicators |
| **Data Quality Signals** | 6.0/10 | Source tooltips on L1 only; QC flags buried; no completeness gauge |
| **Missing Features** | 4.0/10 | No CRM sync, no data verification workflow, no similar companies |
| | | |
| **Composite Score** | **6.2/10** | Data flow bugs mask strong enrichment quality and well-built UI |

---

## Complete Field Gap Mapping

### L1 Enrichment Fields

| Field | Enricher Produces | DB Stores | API Returns | Frontend Renders | Status |
|-------|:-:|:-:|:-:|:-:|--------|
| company_name | Y | Y | Y | Y | OK |
| website | Y | Y | Y | Y | OK |
| industry | Y | Y | Y | Y | OK |
| employee_count | Y | Y | Y | Y | OK |
| hq_city | Y | Y | Y | Y | OK (gaps for some companies) |
| hq_country | Y | Y | Y | Y | OK |
| founded_year | Y | Y | Y | Y | OK |
| description | Y | Y | Y | Y | OK |
| linkedin_url | Y | Y | Y | Y | OK |
| logo_url | Y | Y | Y | N | **P2-2**: Not rendered |
| revenue_estimate | Y | Y | Y | Y | OK (rarely populated) |
| tier | Y | Y | Y | Y | OK |
| status | Y | Y | Y | Y | OK |
| quality_score | N | Y (always 0) | Y | Y | **P3-1**: Never populated |

### L2 Enrichment Fields (Company Intelligence)

| Field | Enricher Produces | Monolithic DB | Split DB | API Returns | Frontend Renders | Status |
|-------|:-:|:-:|:-:|:-:|:-:|--------|
| company_intel | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| key_products | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| customer_segments | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| competitors | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| tech_stack | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| leadership_team | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| certifications | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| recent_news | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| funding_history | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| eu_grants | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| pain_hypothesis | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| ai_opportunities | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| quick_wins | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| industry_pain_points | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| cross_functional_pain | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| adoption_barriers | Y | Y | N | N | Y (built) | **P0-1**: Invisible |
| expansion | Y | Y | N | N | Y (built) | **P0-1 + P1-1**: Missing from split |
| workflow_ai_evidence | Y | Y | N | N | Y (built) | **P0-1 + P1-1**: Missing from split |
| revenue_trend | Y | Y | N | N | Y (built) | **P0-1 + P1-1**: Missing from split |
| growth_signals | Y | Y | N | N | Y (built) | **P0-1 + P1-1**: Missing from split |
| regulatory_pressure | Y | Y | N | N | Y (built) | **P0-1 + P1-1**: Missing from split |
| employee_sentiment | Y | Y | N | N | Y (built) | **P0-1 + P1-1**: Missing from split |
| pitch_framing | Y | Y | N | N | Y (built) | **P0-1 + P1-1**: Missing from split |
| ma_activity | Y | Y | N | N | Y (built) | **P0-1 + P1-1**: Missing from split |
| digital_maturity_score | Y | Y | N | N | Y (built) | **P0-1 + P1-1**: Missing from split |
| it_spend_indicators | Y | Y | N | N | Y (built) | **P0-1 + P1-1**: Missing from split |

### Person Enrichment Fields

| Field | Enricher Produces | DB Stores | API Returns | Frontend Renders | Status |
|-------|:-:|:-:|:-:|:-:|--------|
| role_summary | Y | Y | Y | Y | OK |
| seniority_level | Y | Y | Y | Y | OK |
| decision_authority | Y | Y | Y | Y | OK |
| communication_style | Y | Y | Y | Y | OK |
| professional_background | Y | Y | Y | Y | OK |
| key_responsibilities | Y | Y | Y | Y | OK |
| industry_expertise | Y | Y | Y | Y | OK |
| recent_activity | Y | Y | Y | Y | OK |
| mutual_connections | Y | Y | Y | Y | OK |
| education | Y | N | N | Y (built) | **P0-2**: Discarded |
| certifications | Y | N | N | Y (built) | **P0-2**: Discarded |
| expertise_areas | Y | N | N | Y (built) | **P0-2**: Discarded |
| budget_signals | Y | N | N | Y (built) | **P0-2**: Discarded |
| buying_signals | Y | N | N | Y (built) | **P0-2**: Discarded |
| pain_indicators | Y | N | N | Y (built) | **P0-2**: Discarded |
| technology_interests | Y | N | N | Y (built) | **P0-2**: Discarded |
| personalization_angle | Y | N | N | Y (built) | **P0-2**: Discarded |
| connection_points | Y | N | N | Y (built) | **P0-2**: Discarded |
| conversation_starters | Y | N | N | Y (built) | **P0-2**: Discarded |
| objection_prediction | Y | N | N | Y (built) | **P0-2**: Discarded |
| previous_companies | Y | Y (empty) | Y | Y (built) | **P3-2**: Never mapped |

---

## Cost Efficiency Analysis

| Stage | Cost per Entity | Quality | Verdict |
|-------|----------------|---------|---------|
| L1 (company basics) | ~$0.006 | 6/10 | Cost-effective, acceptable quality |
| Triage (routing) | ~$0.006 | 7.5/10 | Excellent cost/quality ratio |
| L2 (deep intel) | $0.02-$0.06 | 7.5/10 | Excellent depth for cost — but data currently invisible |
| Person | Wasted | 2/10 | 99% failure rate negates all spend |
| Message Gen | ~$0.01 | 8.5/10 | Best quality in pipeline, good cost |
| **Total per company** | **$0.03-$0.08** | | Efficient IF data flow bugs are fixed |

---

## Recommendations — Ranked by Priority and Effort

| Rank | Item | Priority | Effort | Impact | Sprint |
|------|------|----------|--------|--------|--------|
| 1 | Fix L2 write/read mismatch | P0/Must | M | Unlocks 25+ invisible L2 fields for all enriched companies | Sprint 6 |
| 2 | Fix person enrichment 99% failure rate | P0/Must | M | Unblocks entire person enrichment stage | Sprint 6 |
| 3 | Store all person enrichment fields | P0/Must | M | Unlocks 12 additional contact intelligence fields | Sprint 6 |
| 4 | Add missing columns to split L2 tables | P1/Should | S | Prevents future data loss for 12 L2 fields | Sprint 6 |
| 5 | Update API to return new signal fields | P1/Should | S | Makes 6 new signal fields visible in frontend | Sprint 6 |
| 6 | Copy-to-clipboard on all fields | P1/Should | S | Major daily UX improvement for sales reps | Sprint 6 |
| 7 | Structured data quality card | P1/Should | M | Surfaces buried contradictions and research gaps | Sprint 6 |
| 8 | Enrichment completeness gauge | P2/Could | M | Guides users on data readiness | Backlog |
| 9 | Company logo in header | P2/Could | S | Quick visual improvement, low effort | Backlog |
| 10 | Data freshness indicators | P2/Could | S | Prevents stale data from being treated as current | Backlog |
| 11 | Populate quality/confidence scores | P2/Could | S | Enables enrichment quality feedback loop | Backlog |
| 12 | Map previous_companies from career_highlights | P3/Could | S | Fills one more person enrichment gap | Backlog |

---

## Overall Assessment

The enrichment pipeline has strong fundamentals — the LLM prompts are well-designed, cost-efficient, and produce genuinely useful intelligence. The L2 enrichment output (executive briefs, pain hypotheses, AI opportunities, quick wins) would be highly valuable to sales reps IF they could see it. Message generation at 8.5/10 is the pipeline's strongest stage.

However, critical data flow bugs introduced during the migration from monolithic to split table architecture have created a situation where the pipeline generates valuable data that never reaches users. The L2 write/read mismatch alone renders 25+ fields invisible. Person enrichment is almost completely non-functional at a 99% failure rate, and even successful enrichments discard over half their output.

The frontend is well-architected with components already built for all enrichment fields. Fixing the three P0 backend/pipeline bugs would immediately unlock approximately 40+ fields of intelligence that users have never seen, with zero frontend work required.

**Bottom line**: The enrichment pipeline is 80% of the way to being excellent. The remaining 20% is data plumbing bugs that are high-priority but tractable. Sprint 6 should focus exclusively on fixing these data flow issues before any new enrichment features are considered.

| Metric | Value |
|--------|-------|
| Composite Quality Score | 6.2/10 |
| Potential Score (after P0 fixes) | 8.0/10 |
| Fields Currently Invisible | ~40+ |
| Fields Recoverable (no frontend work) | ~37 |
| Estimated Sprint 6 Effort | 3 Must, 4 Should, 5 Could = 12 items |
| P0 Items | 3 (all Sprint 6) |
| P1 Items | 4 (all Sprint 6) |
| P2/P3 Items | 5 (Backlog) |
