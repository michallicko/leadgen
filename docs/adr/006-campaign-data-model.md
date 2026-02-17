# ADR-006: Campaign Data Model
**Date**: 2026-02-17 | **Status**: Accepted

## Context

The leadgen pipeline enriches contacts but had no mechanism to organize them into outreach campaigns. The existing `campaigns` table (from Airtable migration) was minimal — just name, Lemlist ID, and a batch FK. We needed a campaign model that supports:

1. Multi-step message sequences (LinkedIn invite, emails, followups)
2. Template presets for common outreach patterns
3. Contact assignment independent of batches
4. Status machine for campaign lifecycle (draft → generating → review → export)
5. Generation tracking (cost, progress, per-contact status)

## Decision

**Extend existing `campaigns` table** rather than creating a new table. This preserves the existing FK from `messages.campaign_id` and avoids a migration headache.

**Key design choices:**

1. **Campaigns are independent of batches** — contacts are assigned via a junction table (`campaign_contacts`), not by batch membership. This allows cross-batch campaigns.

2. **Template config stored as JSONB** — `template_config` is an ordered array of step definitions. This allows flexible step ordering, toggling, and channel mixing without a rigid relational schema.

3. **System templates + tenant-custom** — `campaign_templates` table with `is_system` flag. System templates (`tenant_id IS NULL`) are visible to all tenants. Tenants can save custom templates.

4. **Status machine with validated transitions** — Campaign status follows a defined lifecycle. The API validates transitions (e.g., can't go from `draft` directly to `review`).

5. **Soft delete** — Deleting a campaign sets `status='archived', is_active=false`. Only draft campaigns can be deleted.

6. **Per-contact tracking** — `campaign_contacts` junction tracks enrichment readiness, generation status, cost, and errors per contact.

## Consequences

- **Positive**: Flexible template system supports future channel additions without schema changes. Junction table enables cross-batch campaigns and per-contact tracking.
- **Positive**: JSONB template config is easy to clone, serialize to/from the frontend, and extend with new fields.
- **Trade-off**: JSONB means we can't enforce step schema at the DB level. Validation happens in application code.
- **Trade-off**: System templates are seeded via migration SQL. Adding new system templates requires a new migration.
- **Future**: BL-035 (Message Generation Engine) will consume the `template_config` to generate messages per step per contact.
