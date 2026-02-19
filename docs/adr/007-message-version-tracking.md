# ADR-007: Message Version Tracking with Structured Edit Feedback

**Date**: 2026-02-19 | **Status**: Accepted

## Context

The message generation system (BL-035) creates draft outreach messages via Claude Haiku API. During review, users need to:

1. Edit messages manually (fix tone, language, factual errors)
2. Regenerate messages with different parameters (language, formality, tone)
3. Capture *why* edits were made, to feed back into LLM prompt improvement

We considered three approaches for tracking changes:

- **Full audit log**: Separate `message_versions` table recording every state change. Maximum flexibility but adds complexity and JOIN overhead for a feature that may not need full history.
- **Diff-based**: Store diffs between versions. Space-efficient but hard to reconstruct original for comparison.
- **Original-snapshot**: Store `original_body`/`original_subject` once (immutable after first set), plus structured edit metadata on the message itself.

## Decision

We chose the **original-snapshot** approach with structured edit reason tags:

- `original_body` / `original_subject`: Set on first edit or regeneration, never overwritten after that. Nullable — null means the message has never been modified.
- `edit_reason`: Enum-like tag from a fixed set of 10 categories (`too_formal`, `too_casual`, `wrong_tone`, `wrong_language`, `too_long`, `too_short`, `factually_wrong`, `off_topic`, `generic`, `other`).
- `edit_reason_text`: Optional free-form text (for `other` or additional context).
- `regen_count` / `regen_config`: Track regeneration history (count + last config used).

The `edit_reason` is required whenever `body` or `subject` changes via the PATCH endpoint. This ensures every manual edit is tagged.

## Consequences

**Positive:**
- Simple schema change (6 columns on existing `messages` table, no new tables)
- Original vs. current comparison always available for the training data pipeline
- Structured tags enable aggregate analysis (e.g., "40% of edits are wrong_tone → adjust prompt")
- No migration complexity — columns are nullable, backward-compatible

**Negative:**
- Only the original is preserved, not intermediate versions. If a message is edited 3 times, we only have first and last.
- `edit_reason` reflects the *last* edit reason, not all reasons over time.
- If full edit history becomes needed later, we'd need to add a `message_edits` table (but the original-snapshot provides the critical first/last pair).

**Trade-off accepted:** For LLM feedback purposes, the original-to-final delta with a structured reason tag captures 90%+ of the training signal. Full edit history can be added later if needed.
