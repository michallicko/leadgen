# ADR-003: ARES Registry Enrichment Architecture

**Date**: 2026-02-16 | **Status**: Accepted

## Context

Czech companies in the database lack official registry data (ICO, legal form, directors, insolvency status). The Czech ARES API provides this data for free. We need to decide:

1. Where to store registry data
2. How to integrate with the pipeline engine (n8n vs direct Python)
3. How to match companies without ICO numbers

## Decision

### Separate table (not enrichment_l2)
Registry data goes into `company_registry_data` rather than extending `company_enrichment_l2` because:
- Different data lifecycle (government registers vs AI-generated research)
- Can be independently refreshed without re-running expensive L2
- 1:1 pattern already established by `company_enrichment_l2` and `contact_enrichment`

### Direct Python calls (not n8n)
ARES enrichment runs as direct HTTP calls from the Flask API, not via n8n webhooks:
- ARES is a simple GET/POST REST API with JSON responses — no workflow orchestration needed
- Zero cost eliminates the need for n8n's execution tracking/retry infrastructure
- Sub-second response times make synchronous single-company lookup viable
- Reduces n8n dependency for non-AI enrichment sources

The pipeline_engine gains a dispatch pattern: `run_stage()` branches on stage name to call either `call_n8n_webhook()` or the ARES service directly.

### Name matching with confidence scoring
When ICO is not available, we search ARES by company name and apply fuzzy matching:
- Strip Czech legal suffixes (s.r.o., a.s., spol. s r.o., k.s., v.o.s., z.s., z.u.)
- Normalize whitespace and case
- Auto-match at >= 0.85 similarity, return candidates at >= 0.60
- Store `match_method` (ico_direct, name_auto, name_manual) and `match_confidence` for audit

### ICO on companies table
Add `ico TEXT` directly to the companies table (not just registry_data) because:
- Enables quick filtering in list views
- Acts as the bridge between our companies and ARES records
- Same pattern as other frequently-queried fields (status, tier, hq_country)

## Consequences

- Pipeline engine becomes more flexible (can dispatch to non-n8n handlers)
- Future enrichment sources (e.g., UK Companies House, German Handelsregister) can follow the same pattern
- Name matching may produce false positives — confidence scoring + manual confirmation mitigates this
- ARES API availability is outside our control — errors are handled gracefully with retry on next run
