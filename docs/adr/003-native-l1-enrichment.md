# ADR-003: Native L1 Enrichment via Perplexity

**Date**: 2026-02-16 | **Status**: Accepted

## Context

L1 company enrichment currently runs via n8n webhook (`/webhook/l1-enrich`). The n8n workflow calls Perplexity for web-grounded research, then runs ~400 lines of JS triage logic. This architecture has several issues:

1. **Testability**: n8n workflows can't be unit tested; we only discover bugs in production
2. **Cost visibility**: n8n provides no per-call cost tracking; we can't attribute costs to tenants
3. **Debugging**: n8n execution logs are ephemeral and hard to search
4. **Version control**: n8n workflow JSON is not in git; changes are hard to review

## Decision

Port L1 enrichment to native Python (`api/services/l1_enricher.py`) that:
- Calls Perplexity sonar API directly via `requests`
- Implements field mapping and QC validation in Python
- Uses `llm_usage_log` for per-call cost tracking
- Stores raw research in `research_assets` table
- Routes through pipeline engine via `DIRECT_STAGES` dispatch

The pipeline engine uses a hybrid approach: L1 runs natively, other stages still call n8n webhooks. The `_process_entity()` function dispatches based on `DIRECT_STAGES` set membership.

**Scope limitation**: This ADR covers enrichment only — no triage logic. Companies get `status='triage_passed'` (clean) or `status='needs_review'` (QC-flagged). Triage will be a separate step.

## Consequences

**Positive**:
- 94 unit tests cover all parsing, mapping, and QC logic
- Per-call cost tracking via `llm_usage_log` with Perplexity pricing
- Research data preserved in `research_assets` for audit and reprocessing
- QC validation catches implausible data before it enters the pipeline
- Review workflow (API + dashboard) for human-in-the-loop QC override

**Negative**:
- Two enrichment paths exist temporarily (Python L1, n8n L2/Person)
- Perplexity API key must be configured on VPS alongside n8n credentials
- `research_assets` table must be created via migration before first use

**Risks**:
- Perplexity API rate limits or pricing changes not automatically handled
- QC thresholds may need tuning based on production data quality
