# ADR-002: AI Column Mapping for CSV Import

**Date**: 2026-02-13 | **Status**: Accepted

## Context

Users import contact lists from various sources (LinkedIn exports, CRM exports, spreadsheets). Each source uses different column names, orderings, and formats. We need a way to map arbitrary CSV columns to our database schema without requiring users to manually configure every mapping.

Options considered:
1. **Manual mapping UI only** — user selects each mapping via dropdowns
2. **Rule-based heuristics** — match column names using keyword patterns
3. **AI-powered mapping** — send headers + sample rows to Claude, get structured mapping

## Decision

Use Claude API (Sonnet) to auto-detect column mappings, with manual override.

The AI receives CSV headers + 5 sample rows and returns a structured JSON mapping with confidence scores, transforms, and warnings. Users can adjust any mapping via dropdowns before proceeding.

Key design choices:
- **Claude Sonnet** (not Opus) for cost efficiency — column mapping is a structured classification task
- **Server-side API call** — keeps API key server-side, consistent latency
- **Graceful degradation** — if AI call fails, user gets empty mapping with a warning and can map manually
- **Enum normalization** — separate step post-mapping, using hardcoded reverse maps (not AI)

## Consequences

**Positive:**
- Near-zero manual effort for well-structured CSVs
- Handles diverse formats (First+Last name, URLs, free-text enums)
- Confidence scores help users spot uncertain mappings
- Manual override preserves full user control

**Negative:**
- Adds `anthropic` Python SDK as a dependency
- Requires `ANTHROPIC_API_KEY` env var in production
- ~2-3 second latency on upload (acceptable for one-time import action)
- Small per-import cost (~$0.002-0.005 per mapping call)

**Risks:**
- AI could hallucinate field names — mitigated by validating against known target fields
- Prompt injection from CSV data — mitigated by structured JSON output parsing
