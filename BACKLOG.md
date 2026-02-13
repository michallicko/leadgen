# Backlog

Structured backlog for the leadgen-pipeline project. Items are prioritized using MoSCoW and tracked with sequential IDs.

**Next ID**: BL-006

## Must Have

### BL-001: Contacts & Companies Screens
**Status**: Done | **Effort**: L | **Spec**: `docs/specs/contacts-companies-screens.md`
**Depends on**: — | **ADR**: `docs/adr/001-virtual-scroll-for-tables.md`

Dashboard screens for browsing, filtering, and viewing contacts and companies from the PostgreSQL database. Replaces direct Airtable access for day-to-day operations. Includes search, status filters, detail views, infinite scroll with virtual DOM windowing.

### BL-002: L1 Workflow Postgres Migration
**Status**: Refined | **Effort**: M | **Spec**: `docs/specs/l1-postgres-migration.md`
**Depends on**: —

Migrate the L1 Company enrichment n8n workflow to write directly to PostgreSQL instead of Airtable. First step in eliminating the Airtable dependency from the enrichment pipeline. Requires n8n Postgres credential setup and workflow node changes.

### BL-003: Full Workflow Migration (L2/Person/Orchestrator)
**Status**: Idea | **Effort**: XL | **Spec**: —
**Depends on**: BL-002

Migrate remaining enrichment workflows (L2 Company, L2 Person, Orchestrator) to write to PostgreSQL. Completes the Airtable-to-Postgres transition. Cannot start until L1 migration (BL-002) is proven stable.

## Should Have

### BL-004: LinkedIn CSV Ingestion
**Status**: In Progress | **Effort**: S | **Spec**: —
**Depends on**: —

Script to import LinkedIn Sales Navigator CSV exports into the contacts/companies tables. Enables bulk contact loading without manual Airtable entry. Handles deduplication by LinkedIn URL.

### BL-005: Stage Runs Tracking
**Status**: In Progress | **Effort**: M | **Spec**: —
**Depends on**: —

Database tables and API endpoints for tracking individual pipeline stage executions (L1, L2, Person). Records timing, status, error details, and cost per stage run. Enables pipeline observability beyond the current progress webhook.

## Could Have

_No items yet._

## Won't Have (for now)

_No items yet._

## Completed

### BL-001: Contacts & Companies Screens (Done 2026-02-13)
Dashboard screens with infinite scroll, virtual DOM windowing, filters, detail modals, inline editing. ADR-001.
